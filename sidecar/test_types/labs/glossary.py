"""
Blood lab results glossary: medical term -> plain English explanation.

Each definition is written at a 6th-8th grade reading level for
patient-facing explanations.
"""

LAB_GLOSSARY: dict[str, str] = {
    # --- General Lab Concepts ---
    "Laboratory Results": (
        "A report showing the results of blood or urine tests. These tests "
        "measure different substances in your body to check how well your "
        "organs are working and to look for signs of disease."
    ),
    "Reference Range": (
        "The range of values that is considered normal for a particular test. "
        "Results outside this range may need further evaluation, but a single "
        "out-of-range result does not always mean something is wrong."
    ),
    "Flag": (
        "A marker on a lab result (usually 'H' for high or 'L' for low) that "
        "shows the value is outside the normal reference range."
    ),
    "Fasting": (
        "Not eating or drinking anything except water for a period of time "
        "(usually 8-12 hours) before a blood test. Some tests, like glucose "
        "and lipids, are more accurate when done fasting."
    ),

    # --- CMP / Chemistry ---
    "Comprehensive Metabolic Panel": (
        "A group of 14 blood tests that gives your doctor important information "
        "about your body's chemical balance, blood sugar, and how well your "
        "kidneys and liver are working. It is often abbreviated as CMP."
    ),
    "Basic Metabolic Panel": (
        "A group of 8 blood tests that checks your blood sugar, kidney function, "
        "and electrolyte levels. It is a smaller version of the comprehensive "
        "metabolic panel. It is often abbreviated as BMP."
    ),
    "Glucose": (
        "The main type of sugar in your blood that your body uses for energy. "
        "High glucose levels may indicate diabetes or prediabetes. Low levels "
        "can cause shakiness, confusion, and fatigue."
    ),
    "BUN": (
        "Blood Urea Nitrogen -- a waste product made when your body breaks down "
        "protein. Your kidneys filter it out of your blood. High BUN levels may "
        "mean your kidneys are not working as well as they should."
    ),
    "Creatinine": (
        "A waste product made by your muscles during normal activity. Your kidneys "
        "filter it from your blood. A high creatinine level may be a sign that "
        "your kidneys are not filtering properly."
    ),
    "eGFR": (
        "Estimated Glomerular Filtration Rate -- a number that estimates how well "
        "your kidneys are filtering waste from your blood. A higher number is "
        "better. A value below 60 may indicate kidney disease."
    ),
    "Sodium": (
        "An electrolyte that helps control the amount of water in your body and "
        "helps your nerves and muscles work properly. It is the same mineral "
        "found in table salt."
    ),
    "Potassium": (
        "An electrolyte that is important for your heart, muscles, and nerves "
        "to work properly. Both very high and very low potassium levels can be "
        "dangerous and affect your heartbeat."
    ),
    "Chloride": (
        "An electrolyte that works with sodium and potassium to help control "
        "the balance of fluids in your body. Abnormal levels may indicate "
        "dehydration or kidney problems."
    ),
    "CO2": (
        "Carbon dioxide (bicarbonate) -- a measure of the acid-base balance in "
        "your blood. Abnormal levels can be caused by kidney disease, lung "
        "disease, or other conditions that affect how your body handles acids."
    ),
    "Calcium": (
        "A mineral that is important for strong bones, muscle movement, nerve "
        "signals, and blood clotting. Most calcium in your blood is attached to "
        "a protein called albumin."
    ),
    "Total Protein": (
        "A measure of all the protein in your blood, including albumin and "
        "globulins. Abnormal levels can be a sign of liver disease, kidney "
        "disease, or problems with your immune system."
    ),
    "Albumin": (
        "The most common protein in your blood, made by your liver. It carries "
        "important substances through your blood and keeps fluid from leaking "
        "out of your blood vessels. Low albumin may indicate liver or kidney problems."
    ),
    "Total Bilirubin": (
        "A yellow substance made when your body breaks down old red blood cells. "
        "Your liver processes bilirubin so it can leave your body. High levels "
        "can cause yellowing of the skin (jaundice) and may indicate liver problems."
    ),
    "AST": (
        "Aspartate Aminotransferase -- an enzyme found mainly in your liver and "
        "heart. When these organs are damaged, AST is released into the blood. "
        "A high level may indicate liver damage, but it can also come from muscle injury."
    ),
    "ALT": (
        "Alanine Aminotransferase -- an enzyme found mainly in your liver. It is "
        "a more specific marker of liver damage than AST. A high ALT level often "
        "points to liver inflammation or injury."
    ),
    "Alkaline Phosphatase": (
        "An enzyme found in your liver, bones, kidneys, and digestive system. "
        "High levels may suggest liver disease, bone disorders, or a blocked "
        "bile duct. It is often abbreviated as ALP."
    ),

    # --- CBC / Hematology ---
    "Complete Blood Count": (
        "A common blood test that measures the different types of cells in your "
        "blood, including red blood cells, white blood cells, and platelets. "
        "It helps detect infections, anemia, and many other conditions."
    ),
    "WBC": (
        "White Blood Cell count -- the number of infection-fighting cells in "
        "your blood. A high count may mean your body is fighting an infection "
        "or inflammation. A low count may mean a higher risk of infection."
    ),
    "RBC": (
        "Red Blood Cell count -- the number of cells that carry oxygen from your "
        "lungs to the rest of your body. Low levels may indicate anemia. High "
        "levels may indicate dehydration or other conditions."
    ),
    "Hemoglobin": (
        "The protein inside red blood cells that carries oxygen. Low hemoglobin "
        "(anemia) can cause tiredness, weakness, and shortness of breath. It is "
        "often one of the first values doctors check."
    ),
    "Hematocrit": (
        "The percentage of your blood that is made up of red blood cells. Low "
        "hematocrit means you have fewer red blood cells than normal (anemia). "
        "High hematocrit can occur with dehydration."
    ),
    "MCV": (
        "Mean Corpuscular Volume -- the average size of your red blood cells. "
        "Large red blood cells (high MCV) may suggest vitamin B12 or folate "
        "deficiency. Small red blood cells (low MCV) may suggest iron deficiency."
    ),
    "MCH": (
        "Mean Corpuscular Hemoglobin -- the average amount of hemoglobin in "
        "each red blood cell. It is related to MCV and helps determine the "
        "type of anemia if present."
    ),
    "MCHC": (
        "Mean Corpuscular Hemoglobin Concentration -- the average concentration "
        "of hemoglobin in your red blood cells. Low MCHC means the cells are "
        "paler than normal, which can happen with iron deficiency."
    ),
    "RDW": (
        "Red Cell Distribution Width -- a measure of how much your red blood "
        "cells vary in size. A high RDW means the cells are more uneven in size, "
        "which can help identify the cause of anemia."
    ),
    "Platelet Count": (
        "The number of platelets (tiny blood cells) that help your blood clot "
        "and stop bleeding. Low platelets can lead to easy bruising and bleeding. "
        "High platelets may increase the risk of blood clots."
    ),
    "MPV": (
        "Mean Platelet Volume -- the average size of your platelets. Larger "
        "platelets are usually younger and more active. MPV can help your doctor "
        "understand the cause of a high or low platelet count."
    ),

    # --- Lipid Panel ---
    "Lipid Panel": (
        "A group of blood tests that measures different types of fats (lipids) "
        "in your blood. It is used to assess your risk of heart disease and "
        "stroke. It usually requires fasting for 9-12 hours before the test."
    ),
    "Total Cholesterol": (
        "The total amount of cholesterol in your blood, including both 'good' "
        "(HDL) and 'bad' (LDL) cholesterol. A lower total cholesterol is "
        "generally better for heart health."
    ),
    "HDL": (
        "High-Density Lipoprotein -- often called 'good' cholesterol because "
        "it helps remove other forms of cholesterol from your blood. Higher "
        "HDL levels are associated with a lower risk of heart disease."
    ),
    "LDL": (
        "Low-Density Lipoprotein -- often called 'bad' cholesterol because "
        "high levels can lead to plaque buildup in your arteries, increasing "
        "the risk of heart attack and stroke."
    ),
    "Triglycerides": (
        "A type of fat in your blood that your body uses for energy. High "
        "triglyceride levels, especially combined with high LDL or low HDL, "
        "can increase your risk of heart disease."
    ),
    "VLDL": (
        "Very Low-Density Lipoprotein -- a type of 'bad' cholesterol that "
        "carries triglycerides through your blood. High VLDL levels contribute "
        "to plaque buildup in your arteries."
    ),

    # --- Thyroid Panel ---
    "Thyroid Panel": (
        "A group of blood tests that checks how well your thyroid gland is "
        "working. The thyroid is a small gland in your neck that controls "
        "your metabolism, energy levels, and many body functions."
    ),
    "TSH": (
        "Thyroid-Stimulating Hormone -- made by a gland in your brain to tell "
        "your thyroid how much hormone to produce. High TSH usually means your "
        "thyroid is underactive (hypothyroidism). Low TSH may mean it is overactive."
    ),
    "Free T4": (
        "Free Thyroxine -- the active form of the main thyroid hormone. Low "
        "Free T4 with high TSH suggests an underactive thyroid. High Free T4 "
        "with low TSH suggests an overactive thyroid."
    ),
    "Free T3": (
        "Free Triiodothyronine -- the most active thyroid hormone. It is "
        "sometimes checked when thyroid disease is suspected but Free T4 is "
        "normal. High levels may confirm an overactive thyroid."
    ),
    "Total T4": (
        "Total Thyroxine -- measures all the T4 hormone in your blood, both "
        "bound to proteins and free. It gives a general picture of thyroid "
        "function but Free T4 is usually a more accurate test."
    ),

    # --- Iron Studies ---
    "Iron Studies": (
        "A group of blood tests that measures how much iron is in your blood "
        "and how well your body is able to use and store it. These tests help "
        "diagnose iron deficiency and other iron-related conditions."
    ),
    "Iron": (
        "A mineral in your blood that is needed to make hemoglobin, the protein "
        "that carries oxygen in red blood cells. Low iron levels can lead to "
        "iron-deficiency anemia, causing fatigue and weakness."
    ),
    "TIBC": (
        "Total Iron-Binding Capacity -- measures how much iron your blood can "
        "carry. A high TIBC means your body is trying to absorb more iron, "
        "which often happens when iron levels are low."
    ),
    "Ferritin": (
        "A protein that stores iron in your body. Low ferritin is one of the "
        "earliest signs of iron deficiency, even before anemia develops. Very "
        "high ferritin can indicate inflammation or iron overload."
    ),
    "Transferrin Saturation": (
        "The percentage of transferrin (an iron-carrying protein) that is "
        "loaded with iron. Low saturation suggests iron deficiency. High "
        "saturation may indicate iron overload."
    ),

    # --- HbA1c ---
    "HbA1c": (
        "Hemoglobin A1c -- a blood test that shows your average blood sugar "
        "level over the past 2-3 months. It is used to diagnose diabetes and "
        "to monitor how well blood sugar is being controlled. A normal level "
        "is below 5.7%."
    ),

    # --- Urinalysis ---
    "Urinalysis": (
        "A test that examines your urine for signs of disease. It checks the "
        "appearance, concentration, and content of urine. It can help detect "
        "kidney disease, urinary tract infections, and diabetes."
    ),
    "Urine pH": (
        "A measure of how acidic or alkaline your urine is. Normal urine pH "
        "ranges from about 4.5 to 8.0. Abnormal levels may be related to "
        "kidney stones, urinary infections, or diet."
    ),
    "Specific Gravity": (
        "A measure of how concentrated your urine is. It shows how well your "
        "kidneys are able to concentrate or dilute urine. Very dilute or very "
        "concentrated urine may indicate a kidney problem or dehydration."
    ),

    # --- Interpretive Terms ---
    "Anemia": (
        "A condition where you do not have enough healthy red blood cells to "
        "carry oxygen to your body's tissues. It can make you feel tired and "
        "weak. Common causes include iron deficiency, vitamin deficiency, and "
        "chronic disease."
    ),
    "Electrolytes": (
        "Minerals in your blood (like sodium, potassium, and chloride) that "
        "carry an electric charge. They are essential for many body functions, "
        "including muscle contraction, heartbeat regulation, and fluid balance."
    ),
    "Liver Function": (
        "A term for blood tests (such as AST, ALT, ALP, and bilirubin) that "
        "check how well your liver is working. These tests measure enzymes and "
        "substances that the liver makes or processes."
    ),
    "Kidney Function": (
        "A term for blood tests (such as BUN, creatinine, and eGFR) that check "
        "how well your kidneys are filtering waste from your blood. Abnormal "
        "results may indicate kidney disease."
    ),
}
