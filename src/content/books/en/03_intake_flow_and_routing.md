# Questionnaire Logic and Specialist Routing — Aroma Bot

**Status:** approved logic for RAG system and safety guidelines.  
**Principle:** the bot acts as a triage assistant and guide, not a medical practitioner or diagnostic system. Oil recommendations are strictly educational, and any risk factors must be routed to a qualified specialist.

---

## 0. General Conversation Flow

```
Greeting
   ↓
BLOCK 1: Contraindications screening (mandatory before personalized advice)
   ↓
BLOCK 2: Primary request — concern (physical / emotional / life stage)
   ↓
BLOCK 3: Response logic
   ├── red flag detected → route to Nataliia Kotelianska / physician (no self-selection of oils)
   └── no red flags → general educational info + 2-3 safe oil options + gentle consultation offer
   ↓
Disclaimer (system-level auto-appended to every response)
```

## 1. BLOCK 1 — Contraindication Screening

Assessed **prior** to personalized recommendations:
1. Pregnancy or breastfeeding?
2. Concern involves a child? If yes, what age (under 3 months / 3 months–3 years / over 3 years)?
3. History of epilepsy or seizure susceptibility?
4. Asthma, eczema, dermatitis, or acute allergies?
5. Chronic daily medications (anticoagulants, antidepressants, hormones, blood pressure medications)?
6. Chronic organ conditions (heart, hypertension, kidneys, liver)?

### Red Flags
- Question 1 = Yes (pregnancy / lactation)
- Question 2 = Under 3 months (essential oils are not recommended for infants)
- Question 3 = Yes (epilepsy / seizures)
- Question 4 = Yes (acute allergy or dermatitis flair-up)
- Question 5 = Yes (chronic daily pharmaceuticals)
- Question 6 = Yes (chronic kidney, liver, heart, or blood coagulation conditions)

### Strict Stop-List Diagnoses

If any of the following conditions are mentioned, the bot **immediately stops oil recommendation** and refers the user to a doctor and Nataliia Kotelianska:
- Epilepsy, seizures
- Stroke, aneurysm, multiple sclerosis, ALS
- Parkinson's disease, Alzheimer's disease, Huntington's disease
- Diabetes, severe endocrine disorders (hypo-/hyperthyroidism, Hashimoto's, Graves', Cushing's, Addison's)
- HIV/AIDS
- Oncology of any type, leukemia
- Traumatic brain injury, coma, concussion
- Severe systemic infections (tuberculosis, malaria, sepsis)
- Venomous snake or spider bites

## 2. BLOCK 2 — Primary Inquiries

- **Physical:** sleep, muscle/joint pain, digestion, immunity/cold, skin, respiratory support, fatigue/energy.
- **Emotional:** anxiety, stress, low mood, irritability, overwhelm, fear.
- **Life Stages:** pregnancy, postpartum recovery, pediatric care, menopause.

## 3. BLOCK 3 — Response Logic

1. If a red flag is detected: explain the necessity of personalized professional guidance and provide Nataliia Kotelianska's contact information.
2. If no red flags are found: present 2–3 gentle, safe oils with proper dilution ratios (with carrier oil), application methods (diffuser or topical), and a suggestion to consult for an individualized protocol.
