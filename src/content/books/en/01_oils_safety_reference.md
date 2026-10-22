# Knowledge Base: Essential Oils — Properties, Indications, Contraindications

**Sources:** "Aromatherapy for Mother and Baby" (A. England, L. Borg), "The Power in Every Drop" (doTERRA)
**Status:** Knowledge base draft for the Aroma Bot. Requires final review by Natalia Kotelyanska before publication—especially Section 4 (divergence between sources).
**Purpose:** Source of facts for bot RAG search and routing logic (see `03_intake_flow_and_routing.md`).

---

## 1. General Safety Rules (Always Apply Before Selecting Any Oil)

- **Pregnancy:** Certain oils stimulate menstruation/uterine contractions or are considered too strong for a pregnant woman's body. During pregnancy, the lowest possible concentration is preferred: **1% oil solution** (about half as many drops as a standard recipe), whereas for other cases the benchmark is **2.5%**. Recommended approximate proportions:
  - Standard concentration (not pregnant): 100 ml carrier oil → 50 drops essential oil; 50 ml → 25 drops; 10 ml → 5 drops.
  - Pregnancy / sensitive skin (≈1%): 100 ml → 25 drops; 50 ml → 12 drops; 10 ml → 2 drops.
- **Epilepsy / Seizure Proneness:** Do not use without specialist approval; fennel, hyssop, common sage, wormwood, and rosemary are specifically noted as increasing risk.
- **Asthma, Eczema, Dermatitis, Allergies:** Prior consultation required—individual reactions vary.
- **Infants under 3 Months:** Essential oils should never be added to bathwater (risk of eye contact due to incomplete dispersion). After 3 months—only heavily diluted and according to specific formulas.
- **General Dilution Rule for Children:** Never exceed formula proportions; more concentrated solutions are not more "effective", but simply more dangerous.
- **Bergamot and Other Citrus Oils (Phototoxicity):** Do not apply prior to sun exposure/tanning/solarium: risk of irregular skin pigmentation.
- **Mucous-Irritating Oils Requiring Special Care During Inhalation/Diffusing:** Clove, cinnamon, lemongrass, thyme.
- Diffusers should not be placed near infants or pregnant women until the specific oil is confirmed safe for that situation.

## 2. Oils to Avoid During Pregnancy

(According to "Aromatherapy for Mother and Baby"; some sources limit this list to the first trimester, but the author recommends avoiding throughout the entire term)

Angelica, anise seed, basil, clove, oregano, jasmine (in pure essential oil form—do not confuse with local labor use, see profile below), Spanish marjoram, hyssop, camphor, cedarwood, cinnamon bark, lovage, marjoram, melissa, myrrh, juniper, peppermint, parsley, tarragon, rosemary, sweet marjoram, thyme, fennel, savory, common sage, clary sage.

Allowed with caveats:
- **Lavender**—gentle, can be used even in early stages.
- **Chamomile** (Roman/German)—allowed, but discontinue if unusual spotting/bleeding occurs.
- **Cypress**—allowed in later stages topically (e.g., for hemorrhoids).

## 3. Oils Not Recommended for Aromatherapy Use in Principle

(Listed as toxic for this mode of application—source: same book; see important note in Section 4 regarding Wintergreen)

Calamus, American bay, armoise, arnica, mustard, bitter almond, wintergreen, shrub wormwood, boldo leaf, jaborandi leaf, savin juniper, pennyroyal, tansy, wormwood, rue, thuja (arborvitae), horseradish.

## 4. ⚠️ Discrepancy Between Sources—Requires Decision by Natalia

Book 1 (clinical aromatherapy) lists **wintergreen** as an oil that should never be used. Meanwhile, doTERRA officially offers wintergreen as a key component of therapeutic-grade pain-relief blends (mentioned in "The Power in Every Drop", "Pain Relief" section).

This is not a parsing error—the discrepancy is real and likely relates to purity/dilution standards between the conventional essential oil market and doTERRA CPTG standards. **The bot must not resolve this conflict on its own**—for wintergreen (and any conflicting source cases), strictly route to Natalia rather than issuing bot recommendations.

## 5. Oil Profiles (Book 1, Complete Reference)

Format: Oil (Latin) — Properties — Main Application (brief) — **Applicability by Stage: Pre-conception / Pregnancy / Labor / Postpartum / Children**

| Oil | Key Properties | Application (brief) | Pre-conception | Pregnancy | Labor | Postpartum | Children |
|---|---|---|---|---|---|---|---|
| Benzoin | antiseptic, expectorant, warming | respiratory congestion, cracked skin, nipples postpartum | no | no | no | yes | no |
| Bergamot | antiseptic, antidepressant, antispasmodic | mood, skin infections, cystitis; ⚠️ phototoxic | no | yes (limited, cystitis) | no | yes | no |
| Roman/German Chamomile | anti-inflammatory, antispasmodic, mild sedative | skin issues, muscle and menstrual pain, infant colic, sleep | no | yes | no | yes | yes |
| Clary Sage | antispasmodic, hormone-balancing | PMS, menopause, postpartum blues; ⚠️ do not combine with driving/alcohol | yes | **no** | yes | yes | no |
| Cypress | astringent, diuretic | varicose veins, hemorrhoids, edema | no | yes (after 5 mos.) | no | yes | no |
| Eucalyptus | antiseptic, anti-inflammatory | respiratory tract, fever; use at 1:100+ dilution | no | yes | no | no | yes |
| Geranium | balancing, antidepressant | hormonal balance, fluid retention, skin; ⚠️ uplifting—avoid at bedtime | yes | yes (mild solutions; locally after 5 mos.) | yes | yes | no |
| Jasmine | antispasmodic, labor analgesic | labor contraction relief, lactation, libido | yes | **no** | yes | yes | no |
| Lavender | universal: antiseptic/antidepressant/sedative | wounds, sleep, contractions, infant colic | no | yes | yes | yes | yes |
| Lemon | antiseptic, astringent | skin tone, nausea, warts (external) | no | yes | no | yes | no |
| Mandarin / Tangerine | gentle, digestive | GI discomfort, edema, suitable for elderly and children | no | yes | yes | yes | yes |
| Sweet Marjoram | sedative, analgesic | insomnia, muscle aches, PMS; ⚠️ lowers libido | no | **no** | no (sometimes early labor) | yes | no |
| Neroli | antidepressant, sedative | anxiety, panic, skincare | yes | yes | yes | yes | not specified |
| Petitgrain | mild neroli alternative | refreshing, oily skin | no | yes | no | yes | no |
| Rose | antidepressant, tonic | grief, PMS, menopause, skin | yes | **no** | yes | yes | yes |
| Rosemary | stimulating, astringent | circulation, memory, hair; ⚠️ contraindicated in epilepsy | no | **no** | no | yes | no |
| Sandalwood | antiseptic, sedative | urinary tract infections, cough, skin | yes | yes | no | no | no |
| Tea Tree | antiseptic, antifungal | skin infections, blemishes, candida | no | yes | no | no | yes |
| Ylang Ylang | antidepressant, hypotensive | anxiety, palpitations, skin | yes | yes | yes | yes | no |

## 6. Quick Symptom Reference Guide (Book 2, doTERRA)

| Request / Complaint | Recommended Oils & Blends |
|---|---|
| Acne, skin blemishes | Tea Tree, HD Clear blend |
| Allergies | Lavender, Lemon, Peppermint, Breathe blend, GI detox cleanse |
| Insomnia | Lavender, Serenity blend, sleep complex |
| Painful menstruation | ClaryCalm blend, PastTense blend |
| Headache | Peppermint, Lavender, Deep Blue blend, PastTense blend |
| Cough / Cold | Breathe blend, On Guard blend, Tea Tree, Oregano, Frankincense |
| Focus & Attention | InTune blend, Rosemary, Peppermint, Basil |
| Digestive issues | Peppermint, Ginger, DigestZen blend, enzymes, probiotics |
| Cuts / Wounds | Lavender, Tea Tree, antibacterial ointment |
| Sprains, muscle soreness | Lemongrass, Deep Blue blend/rub, Helichrysum, Lavender |
| Respiratory issues | Breathe blend, Eucalyptus, Lemon, Frankincense |
| Insect bites | Lavender, TerraShield blend, Purify blend |
| Ear discomfort | Tea Tree, Basil, Geranium (around the ear, never inside canal) |
| Emotional support | Serenity blend, Balance blend, Citrus Bliss, emotional aromatherapy kit |

## 7. Topic Categories (For Bot Intake Interface)

User inquiries naturally divide into: **Sleep · Pain/Muscles · Digestion · Immunity/Cold · Skin · Respiration · Focus/Energy · Emotional Balance · Home Care · Children · Pets**. Home care and pets are non-medical topics and can be addressed without contraindication screening.
