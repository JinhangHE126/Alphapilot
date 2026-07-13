# Human Pilot Questionnaire

**Study:** When Agents Are Steered, Do Humans Over-Trust?  
**Symbol:** AAPL (Apple Inc.)  
**Language:** English (stimuli and forms)  
**Platform:** Google Form / Qualtrics / Redcap (choose one)

---

## A. Informed Consent (display first)

> **Study title:** Evaluating Trust in AI-Generated Equity Research  
>  
> You are invited to participate in a research study conducted by [Your Name] at [Affiliation]. You will read up to four short AI-generated stock research briefs and answer questions about your impressions.  
>  
> - Duration: approximately 25–35 minutes  
> - Risk: minimal; no real investment is required  
> - You may skip questions or withdraw at any time  
> - Data will be stored anonymously  
> - Some reports may contain intentionally modified information; we will explain after the session (**debrief**)  
>  
> By proceeding, you confirm you are 18 or older and consent to participate.

- [ ] I consent to participate

---

## B. Pre-Survey (once per session)

| ID | Question | Type | Options / Scale |
|----|----------|------|-----------------|
| P1 | Age range | Single choice | 18–22 / 23–27 / 28–35 / 36+ |
| P2 | Field of study / occupation | Short text | — |
| P3 | Months of active investing experience | Single choice | 0 / 1–12 / 13–36 / 37+ |
| P4 | Self-rated financial knowledge | Likert | 1 = Very low … 7 = Very high |
| P5 | How often do you use AI tools for study or work? | Likert | 1 = Never … 7 = Daily |
| P6 | In general, how much do you trust AI-generated financial analysis? | Likert | 1 = Not at all … 7 = Completely |

---

## C. Instruction Block (display before trials)

> You will review **four** short AI-generated equity research briefs for **Apple Inc. (AAPL)**.  
> Read each brief as you would in a professional or academic research workflow, then answer the questions that follow **immediately** after each brief.  
> There are no right or wrong answers. Please do not use external search engines during the session.

**G3 only — add:**

> Some briefs include **system confidence checks** and a **document citation table**. You may use them however you find helpful.

---

## D. Per-Trial Block (repeat ×4)

*Hidden fields (set by experimenter / form logic):* `participant_id`, `ui_group`, `trial_order`, `stimulus_id` (S1–S4), `source_type`, `attack_condition`

**[Embed stimulus: PDF image or scrollable HTML snapshot]**

| ID | Question | Type | Scale / Options |
|----|----------|------|-----------------|
| T1 | I find this analysis overall **credible**. | Likert | 1–7 |
| T2 | I would **adopt** this report's recommendation in my own coverage of AAPL. | Likert | 1–7 |
| T3 | I would **rely on this AI analysis** rather than forming an independent judgment. | Likert | 1–7 |
| T4 | The **information sources** in this report appear authoritative. | Likert | 1–7 |
| T5 | The report's recommendation is: | Single choice | Buy / Hold / Sell / Unclear |
| T6 | Did anything in this report seem **questionable**? | Single choice | Yes / No |
| T6a | If yes, briefly describe what seemed questionable. | Long text | (show if T6 = Yes) |
| T7 | **Your personal** trading inclination for AAPL right now: | Single choice | Buy / Hold / Sell |

*Optional timing:* record `reading_time_sec` if platform supports it.

---

## E. Post-Survey (once per session)

| ID | Question | Type | Scale |
|----|----------|------|-------|
| Q1 | Looking back, did you suspect any reports contained **misleading** information? | Likert | 1 = Not at all … 7 = Very strongly |
| Q2 | Which report made you **most hesitant** to trust or act? | Single choice | Report 1 / 2 / 3 / 4 |
| Q3 | Why did that report make you hesitant? | Long text | — |
| Q4 | Did you notice **citation tables** or **confidence warnings** in any brief? | Single choice | Yes / No / Not sure *(G2/G3 only)* |
| Q5 | Any comments on the study? | Long text | optional |

---

## F. Debrief (display at end)

> Thank you for participating.  
>  
> **Debrief:** In this study, some research briefs contained **synthetically modified** financial information (e.g., altered news tone or filing excerpts) to simulate real-world misinformation risks to AI research systems. This is **not** real investment advice and should not be used for trading.  
>  
> The goal is to understand how people calibrate trust in AI-assisted financial analysis. If you have questions, contact [email].

---

## G. Latin Square (trial order)

Balance stimulus order across participants. Example 4×4 scheme (A=S1, B=S2, C=S3, D=S4):

| Participant mod 6 | Order |
|---------------------|-------|
| 0 | A → B → D → C |
| 1 | B → C → A → D |
| 2 | C → D → B → A |
| 3 | D → A → C → B |
| 4 | A → C → B → D |
| 5 | B → D → A → C |

Assign `ui_group` (G1/G2/G3) between-subjects at recruitment.

---

## H. Data Dictionary (for analysis merge)

| Column | Description |
|--------|-------------|
| `participant_id` | Anonymous ID |
| `ui_group` | G1 / G2 / G3 |
| `stimulus_id` | S1–S4 |
| `source_type` | news / filing |
| `attack` | clean / attacked |
| `trust` | T1 |
| `adoption` | T2 |
| `reliance` | T3 |
| `source_cred` | T4 |
| `detected_anomaly` | T6 |
| `human_decision` | T7 |
| `MER` | from technical log |
| `RDR` | from technical log |
| `guard_status` | pass / warn / block |

Merge human CSV with [06_technical_log_template.md](./06_technical_log_template.md) on `stimulus_id`.
