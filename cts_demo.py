# -*- coding: utf-8 -*-
"""
Created on Tue May 16 23:41:58 2023

@author: vmurc
"""
import streamlit as st
import pandas as pd
import spacy
import en_core_sci_sm
import re
import copy

st.set_page_config(layout="wide")

#Load language model
nlp = en_core_sci_sm.load()

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

    profile = {"inclusion": {}, "exclusion": {}}

    for category in ['inclusion', 'exclusion']:
        for criterion in criteria_dict[category]:
            doc = nlp(criterion)
            if "age" in doc.text.lower():
                match = re.search("age\s*>\s*(\d+)", doc.text.lower())
                if match:
                    profile[category]["age"] = int(match.group(1))
            if "informed consent" in doc.text.lower():
                profile[category]["consent"] = True
            if "lung cancer" in doc.text.lower() or "ggo" in doc.text.lower():
                profile[category]["diagnosis"] = 'lung cancer'
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

    return profile

#Calculate Sorensen-Dice Index between patient profile and clinical trial
def calculate_match_index(patient, trial_criteria):
    matched_criteria = 0
    total_criteria = 0

    for criterion, value in trial_criteria['inclusion'].items():
        if criterion in patient:
            if isinstance(value, bool) and patient[criterion] == value:
                matched_criteria += 1
                print(f"{criterion} matched. SDI: 1.0")
            elif isinstance(value, int) or isinstance(value, float) and patient[criterion] >= value:
                matched_criteria += 1
                print(f"{criterion} matched. SDI: 1.0")
            elif isinstance(value, list) and isinstance(patient[criterion], list):
                if all(item in patient[criterion] for item in value):
                    matched_criteria += 1
                    print(f"{criterion} matched. SDI: 1.0")
            else:
                print(f"{criterion} not matched. Patient: {patient[criterion]}, Criterion: {value}")
        else:
            print(f"{criterion} not in patient profile.")
        total_criteria += 1

    match_index = matched_criteria / total_criteria if total_criteria > 0 else 0
    print(f"Total SDI: {match_index}")
    return match_index

#Process ages in text
def extract_age_requirement(criteria):
    match = re.search(r'Age (\d+) - (\d+)', criteria)
    if match:
        min_age = int(match.group(1))
        max_age = int(match.group(2))
        return min_age, max_age
    else:
        return None, None

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
    pregnant    = st.selectbox('Pregnant?', (True, False))
    psychiatric = st.selectbox('Psychiatric Disorders?', (True, False))
    irradiation = st.selectbox('Undergoing irradiation?', (True, False))
    
with col3:
    lactating = st.selectbox('Lactating?', (True, False))
    mpe       = st.selectbox('Malignant Plural Effusion?', (True, False))
    consent   = st.selectbox('Can provide consent?', (True, False))
with col4:
    diagnosis = st.selectbox('Enter diagnosis',("lung cancer", "leukemia", "malaria"))
    infection = st.selectbox('Active infection?', (True, False))
    fdgpet    = st.selectbox('Scheduled for FDG-PET?', (True, False))

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
    sdi = calculate_match_index(patient_profile, trial_criteria)
    # Display final score
    st.write(f'The patient match score for the trial is {sdi}')
    
    #Display the profiles for the patient and clinical trial
    col5, col6 = st.columns(2)
    with col5:
        st.write('This is the patient profile \n',patient_profile)
    with col6:
        st.write('This is the CT profile \n',trial_criteria)