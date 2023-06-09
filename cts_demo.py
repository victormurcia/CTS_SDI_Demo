# -*- coding: utf-8 -*-
"""
Created on Tue May 16 23:41:58 2023

@author: vmurc
"""
import streamlit as st
import spacy
import en_core_sci_sm
import re
import copy
#from negspacy.negation import Negex

st.set_page_config(layout="wide")

#Load language model
nlp = en_core_sci_sm.load()
#nlp.add_pipe("negex", last=True)


#This function breaks the eligibility critiera into inclusion and exclusion criteria
def extract_eligibility_criteria_scispacy(criteria):
    lines = criteria.split("\n")
    eligibility = {"inclusion": [], "exclusion": []}
    current_section = None

    for line in lines:
        doc = nlp(line.strip())
        if "inclusion criteria" in doc.text.lower():
            current_section = "inclusion"
            continue
        elif "exclusion criteria" in doc.text.lower():
            current_section = "exclusion"
            continue

        if current_section and doc.text.strip():
            eligibility[current_section].append(doc.text.strip())

    return eligibility

#This function creates the dictionary for the patient profile based on a text description
def extract_patient_info_scispacy(profile):
    doc = nlp(profile)

    patient = {}

    # Extracting age using regex since NER is not very effective for it
    age = re.search("(\d+)-year-old", profile)
    patient["age"] = int(age.group(1)) if age else None

    for ent in doc.ents:
        if ent.label_ in ['DISEASE', 'CANCER']:
            patient["diagnosis"] = "lung cancer" in ent.text.lower()
        elif "fdg-pet" in ent.text.lower():
            patient["scheduled_for_FDG-PET"] = True
        elif "performance status" in ent.text.lower():
            patient["performance_status"] = int(re.search("(\d)", ent.text).group(1))
        elif "pregnant" in ent.text.lower() or "lactating" in ent.text.lower():
            patient["pregnant_or_lactating"] = True
        elif "malignant pleural effusion" in ent.text.lower():
            patient["malignant_pleural_effusion_only"] = True
        elif "irradiation" in ent.text.lower():
            patient["undergoing_irradiation"] = True
        elif "infections" in ent.text.lower():
            patient["active_infection"] = True
        elif "neurological" in ent.text.lower() or "psychiatric disorders" in ent.text.lower():
            patient["neurological_or_psychiatric_disorders"] = True
        elif "informed consent" in ent.text.lower():
            patient["consent"] = True

    # Assume False if the keys not found
    for key in ["diagnosis", "scheduled_for_FDG-PET", "performance_status", "pregnant_or_lactating", "malignant_pleural_effusion_only", "undergoing_irradiation", "active_infection", "neurological_or_psychiatric_disorders", "consent"]:
        if key not in patient:
            patient[key] = False

    return patient

#Generate criteria profile for clinical trial
def generate_criteria_profile(criteria_dict):
    nlp = en_core_sci_sm.load()

    profile = {"inclusion": {}, "exclusion": {}}

    for category in ['inclusion', 'exclusion']:
        for criterion in criteria_dict[category]:
            doc = nlp(criterion)
            if "age" in doc.text.lower():
                match = re.search(r'age\s*(\d+)\s*-\s*(\d+)', doc.text.lower())
                if match:
                    profile[category]["min_age"] = int(match.group(1))
                    profile[category]["max_age"] = int(match.group(2))
                else:
                    match = re.search("age\s*>\s*(\d+)", doc.text.lower())
                    if match:
                        profile[category]["min_age"] = int(match.group(1))
                    else:
                        match = re.search("age\s*<\s*(\d+)", doc.text.lower())
                        if match:
                            profile[category]["max_age"] = int(match.group(1))
            if "informed consent" in doc.text.lower():
                profile[category]["consent"] = True
            if "lung cancer" in doc.text.lower() or "ggo" in doc.text.lower():
                profile[category]["diagnosis"] = True
            if "fdg-pet" in doc.text.lower():
                profile[category]["scheduled_for_FDG-PET"] = True
            if "performance status" in doc.text.lower():
                match = re.findall("(\d)", doc.text.lower())
                if match:
                    profile[category]["performance_status"] = list(map(int, match))
            if "pregnant" in doc.text.lower() or "lactating" in doc.text.lower():
                profile[category]["pregnant_or_lactating"] = True
            if "malignant pleural effusion" in doc.text.lower():
                profile[category]["malignant_pleural_effusion_only"] = True
            if "irradiation" in doc.text.lower():
                profile[category]["undergoing_irradiation"] = True
            if "infections" in doc.text.lower():
                profile[category]["active_infection"] = True
            if "neurological" in doc.text.lower() or "psychiatric disorders" in doc.text.lower():
                profile[category]["neurological_or_psychiatric_disorders"] = True
    
    profile['exclusion'].pop("scheduled_for_FDG-PET", None)
    return profile

#Calculate Sorensen-Dice Index between patient profile and clinical trial
def calculate_sorensen_dice_index(patient_profile, trial_profile):
    # Extract 'inclusion' and 'exclusion' criteria from trial profile
    inclusion_criteria = trial_profile['inclusion']
    exclusion_criteria = {k: not v for k, v in trial_profile['exclusion'].items()}

    # Check if any key that is True in patient profile is also present in the exclusion criteria
    excluded_keys = [key for key, value in patient_profile.items() if value and key in exclusion_criteria]
    if excluded_keys:
        print(f"Patient is excluded due to criteria: {excluded_keys}")
        return 0

    # Only include keys from patient_profile that are also present in the inclusion criteria
    patient_profile = {key: value for key, value in patient_profile.items() if key in inclusion_criteria}
    # Merge 'inclusion' and 'exclusion' criteria into a single set for comparison
    trial_set = set(inclusion_criteria.items())# | set(exclusion_criteria.items())

    # Convert patient profile to a set
    patient_set = set(patient_profile.items())

    # Calculate the Sorensen-Dice Index
    intersection = len(patient_set & trial_set)
    sdi = 2. * intersection / (len(patient_set) + len(trial_set))
    
    return sdi

#Determine whether patient is a good match or not for clinical trial
def match_patient_to_trial(patient_profile, trial_profile):
    
    #Create a deepcopy of the trial_profile dictionary. Needed to ensure original dictionary is not overwritten
    final_trial_criteria  = copy.deepcopy(trial_profile)
    final_patient_profile = copy.deepcopy(patient_profile)
    # Check age first
    min_age = final_trial_criteria['inclusion'].get("min_age")
    max_age = final_trial_criteria['inclusion'].get("max_age")
    patient_age = patient_profile.get("age")
    if min_age is not None:
      if (patient_age <= min_age):
          age_check1 = False
      else:
        age_check1 = True
    else:
      age_check1 = True

    if max_age is not None:
      if (patient_age >= max_age):
        age_check2 = False
      else:
        age_check2 = True
    else:
        age_check2 = True

    age_check = all([age_check1,age_check2])
    final_trial_criteria['inclusion']['age'] = True
    final_patient_profile['age'] = age_check

    # Check performance score
    min_performance_score = final_trial_criteria['inclusion'].get("performance_status")[0]  
    max_performance_score = final_trial_criteria['inclusion'].get("performance_status")[-1]
    patient_performance_score = patient_profile.get("performance_status")

    if patient_performance_score < min_performance_score or patient_performance_score > max_performance_score:
      final_trial_criteria['inclusion']['performance_status'] = True
      final_patient_profile['performance_status'] = False
    else: 
      final_trial_criteria['inclusion']['performance_status'] = True
      final_patient_profile['performance_status'] = True
    
    #Check diagnosis
    #ct_diagnosis = trial_profile['inclusion'].get("diagnosis")
    pt_diagnosis = final_patient_profile.get("diagnosis")

    if pt_diagnosis == 'lung cancer':
      final_patient_profile["diagnosis"] = True
      final_trial_criteria['inclusion']['diagnosis'] = True
    else: 
      final_patient_profile["diagnosis"] = False
      final_trial_criteria['inclusion']['diagnosis'] = True

    # Remove unnecessary keys
    keys_to_remove = ['min_age', 'max_age']
    for key in keys_to_remove:
        final_trial_criteria['inclusion'].pop(key, None)
    keys_to_remove = ['consent']
    for key in keys_to_remove:
        final_trial_criteria['exclusion'].pop(key, None)
    #Calculate SDI
    sdi = calculate_sorensen_dice_index(final_patient_profile, final_trial_criteria)
    return sdi,final_patient_profile,final_trial_criteria

#Streamlit code
st.title('Clinical Trial Matcher')
st.text('This application shows how the Sorensen-Dice Index (SDI) can be used to quantify the match quality between a patient and a clinical trial.')
url = "https://clinicaltrials.gov/ct2/show/NCT05617742"
st.write('In this demo, the user can change a variety of patient attributes like age, pregnant status, and others and see how that changes the SDI for clinical trial [NCT05617742](%s)' % url)
#Show Sorensen-Dice Equation
latext = r'''
$$
SDI = \frac{2\left | A \cap B \right |}{\left | A \right | + \left | B \right |}
$$ 
'''
st.write(latext)
st.text('The SDI compares two sets (i.e., collections of stuff) by looking at the common elements between the sets and dividing that by the size of the sets.')

#Define eligibility criteria for clinical trial
eligibility_criteria = """
Inclusion Criteria:
    Age > 20 years
    Informed consent obtained from patients and families
    Patients with histology confirmed lung cancer or patients with GGO on chest CT planned to have biopsy or surgery
    Patients scheduled to undergo FDG-PET examination
    Performance status: 0, 1, 2, 3

Exclusion Criteria:
    Contraindication to FAPI-PET and FDG-PET such as pregnant, or lactating patients
    Patients with mainly malignant pleural effusion without other measurable lesions
    Undergoing irradiation at accrual
    Active infection or other serious underlying medical conditions not compatible with study entry
    History of significant neurological or psychiatric disorders including dementia that would prohibit the understanding and giving of informed consent
"""

#Extract inclusion and exclusion criteria from eligibility criteria
st.header('Eligibility Criteria for Clinical Trial')
eligibility = extract_eligibility_criteria_scispacy(eligibility_criteria)
#Show eligibility criteria for current trial
st.text(eligibility_criteria)

# Define column grid
col1, col2, col3, col4 = st.columns(4)
# User inputs
with col1:
    age          = st.number_input('Patient age', min_value=0, max_value=120, step=1)
    neurological = st.selectbox('Neurological Disorders?', (True, False))
    ps           = st.selectbox('Performance Score?', (0,1,2,3,4))
    
with col2:
    fdgpet    = st.selectbox('Scheduled for FDG-PET?', (True, False))
    pregnant    = st.selectbox('Pregnant?', (True, False))
    psychiatric = st.selectbox('Psychiatric Disorders?', (True, False))
    
with col3:
    consent   = st.selectbox('Can provide consent?', (True, False))
    lactating = st.selectbox('Lactating?', (True, False))
    mpe       = st.selectbox('Malignant Plural Effusion?', (True, False))
with col4:
    diagnosis = st.selectbox('Enter diagnosis',("lung cancer", "leukemia", "malaria"))
    infection = st.selectbox('Active infection?', (True, False))
    irradiation = st.selectbox('Undergoing irradiation?', (True, False))
    
eligibility_threshold = st.number_input('Select eligibility threshold', min_value=0, max_value=100, step=10)
#Define the patient profile based on user inputs
patient_profile_text = f"John Doe is a {age}-year-old male who has been diagnosed with {diagnosis}. \
His diagnosis was confirmed through histological examination. \
He has a ground-glass opacity (GGO) on his chest CT scan and is scheduled for biopsy and FDG-PET examination.\
He is not {pregnant} or {lactating}, and he does not only have {mpe}. \
He is not undergoing irradiation and has no active infections or serious underlying medical conditions. \
He has no history of significant neurological or psychiatric disorders. \
He and his family have provided informed consent for treatments and procedures. \
His performance status is 1."

#Check if patient has neurological or psychiatric disorders
norpd = any([psychiatric,neurological])
#Check if patient is pregnant or lactating
porl  = any([pregnant,lactating])

#Patient Profile
patient_profile = {'age': age,
 'scheduled_for_FDG-PET': fdgpet,
 'pregnant_or_lactating': porl,
 'undergoing_irradiation': irradiation,
 'active_infection': infection,
 'neurological_or_psychiatric_disorders': norpd,
 'diagnosis': diagnosis,
 'performance_status': ps,
 'malignant_pleural_effusion_only': mpe,
 'consent': consent}

# Button to calculate match
if st.button('Calculate Match'):
    # Test with a patient profile and trial criteria
    trial_criteria = generate_criteria_profile(eligibility)
    sdi,final_patient_profile,final_trial_criteria = match_patient_to_trial(patient_profile, trial_criteria)
    sdi *= 100
    
    #Determine if patient is eligible for clinical trial based on SDI and eligibility threshold
    if sdi >= eligibility_threshold:
        eligibility = 'eligible'
    else:
        eligibility = 'not eligible'
        
    # Display eligibility assessment
    st.write(f'The patient match score for the trial is {sdi}%. The eligibility threshold has been set to {eligibility_threshold} and so the patient is {eligibility} for this trial')
    
    #Display the profiles for the patient and clinical trial
    col5, col6 = st.columns(2)
    with col5:
        st.write('This is the patient profile \n',final_patient_profile)
    with col6:
        st.write('This is the CT profile \n',final_trial_criteria)