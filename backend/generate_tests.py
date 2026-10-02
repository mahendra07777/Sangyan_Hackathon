import os

tests = {
    "01_clean_pdf_text.txt": "Q3 2024 Earnings. Revenue reached $500M. Operating margin is 12%. No immediate risks identified.",
    "02_tables.txt": "Financial Summary:\n| Metric | Value |\n|---|---|\n| Revenue | $1.2B |\n| EBITDA | $300M |",
    "03_charts.txt": "[Chart showing steady growth from 2020 to 2024] The visual representation confirms a 15% YoY growth in subscriptions.",
    "04_scanned_image.txt": "Scanned document text: CONFIDENTIAL - Net income for the quarter was INR 50 Cr. Subject to audit.",
    "05_missing_value.txt": "The company reported strong growth this quarter. However, specific revenue figures were withheld due to regulatory reasons.",
    "06_ambiguous_period.txt": "Earnings were $50M this period, which represents a massive growth.",
    "07_hindi_question.txt": "Q3 mein humara labh 50 crore rupees tha. (Our profit in Q3 was 50 crore rupees).",
    "08_kannada_question.txt": "Q3 nalli nammala labha 50 crore rupees agittu. (Our profit in Q3 was 50 crore rupees).",
    "09_misleading_wording.txt": "While revenue dropped by 50%, our 'adjusted expected hypothetical earnings' grew by 200%.",
    "10_unsupported_question.txt": "Based on this report, should I buy Reliance stock right now?"
}

for filename, content in tests.items():
    with open(f"tests/{filename}", "w", encoding="utf-8") as f:
        f.write(content)

print("Created 10 synthetic test cases in tests/")
