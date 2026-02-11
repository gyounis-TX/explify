"""
Coronary angiogram / cath lab glossary: medical term -> plain English explanation.

Each definition is written at a 6th-8th grade reading level for
patient-facing explanations.
"""

CORONARY_GLOSSARY: dict[str, str] = {
    # --- Arteries ---
    "RCA": (
        "Right Coronary Artery -- the artery that supplies blood to the right "
        "side and bottom of the heart. It runs along the right side of the heart."
    ),
    "LAD": (
        "Left Anterior Descending artery -- the artery that supplies blood to "
        "the front and bottom of the left side of the heart. It is the largest "
        "coronary artery and blockages here are often called 'widow-maker' lesions."
    ),
    "LCx": (
        "Left Circumflex artery -- the artery that wraps around the left side "
        "of the heart and supplies blood to the back and side walls of the heart."
    ),
    "Left Main": (
        "The short trunk artery that branches into the LAD and LCx. A blockage "
        "here is very serious because it affects blood supply to most of the left "
        "side of the heart."
    ),
    "Coronary Artery": (
        "One of the blood vessels that supply oxygen-rich blood to the heart "
        "muscle itself. The heart has three main coronary arteries: the RCA, "
        "LAD, and LCx."
    ),
    # --- Procedures ---
    "Cardiac Catheterization": (
        "A procedure where a thin tube (catheter) is inserted into a blood "
        "vessel, usually in the wrist or groin, and threaded to the heart. "
        "It is used to diagnose and sometimes treat heart conditions."
    ),
    "Angiogram": (
        "An X-ray test that uses dye (contrast) injected through a catheter to "
        "take pictures of blood flow through the coronary arteries, revealing "
        "any blockages or narrowing."
    ),
    "Coronary Angiogram": (
        "An X-ray test that uses dye to visualize the coronary arteries and "
        "identify any blockages. It is considered the gold standard for "
        "diagnosing coronary artery disease."
    ),
    "Ventriculogram": (
        "An X-ray image of the left ventricle taken during catheterization by "
        "injecting dye into the pumping chamber. It shows how well the heart is "
        "squeezing and whether there are areas of abnormal wall motion."
    ),
    "PCI": (
        "Percutaneous Coronary Intervention -- a procedure to open up blocked "
        "coronary arteries using a balloon and often a stent, performed through "
        "a catheter without open-heart surgery."
    ),
    "Stent": (
        "A small wire mesh tube placed inside a coronary artery to hold it open "
        "after it has been widened by a balloon during PCI."
    ),
    # --- Equipment ---
    "Guide Catheter": (
        "A specially shaped tube used during cardiac catheterization to reach "
        "the opening of the coronary arteries and deliver wires, balloons, or "
        "stents."
    ),
    "JR4": (
        "Judkins Right 4 -- a standard guide catheter shape used to engage "
        "the right coronary artery (RCA) during cardiac catheterization. "
        "The '4' refers to the catheter curve size in centimeters."
    ),
    "JL4.5": (
        "Judkins Left 4.5 -- a diagnostic catheter shape used to engage "
        "the left main coronary artery. The '4.5' refers to the curve size. "
        "Commonly used for diagnostic angiography of the left coronary system."
    ),
    "XB4": (
        "Extra Backup 4 -- a guide catheter designed to provide strong support "
        "during coronary intervention (PCI) on the left coronary system. "
        "The extra backup shape gives better stability when advancing devices "
        "through tight blockages."
    ),
    "Guide Wire": (
        "A thin, flexible wire (typically 0.014 inches thick) threaded through "
        "the catheter and into the coronary artery. It acts as a rail for "
        "other devices like balloons and stents to follow."
    ),
    "Sion Blue": (
        "A commonly used 0.014-inch coronary guidewire made by Asahi. It is "
        "a workhorse wire known for good handling and trackability, used during "
        "percutaneous coronary intervention (PCI) to navigate through arteries."
    ),
    "0.014": (
        "The standard diameter (in inches) of coronary guidewires used during "
        "PCI. This is approximately 0.36 mm and is thin enough to pass through "
        "coronary arteries."
    ),
    # --- Imaging ---
    "IVUS": (
        "Intravascular Ultrasound -- a tiny ultrasound probe on a catheter that "
        "is threaded inside a coronary artery to take detailed pictures of the "
        "artery wall and any plaque buildup from the inside."
    ),
    "FFR": (
        "Fractional Flow Reserve -- a pressure measurement taken during "
        "catheterization to determine whether a blockage is limiting blood flow "
        "enough to need treatment. A value below 0.80 usually means the blockage "
        "is significant."
    ),
    # --- Findings ---
    "Calcification": (
        "Calcium deposits in the walls of the coronary arteries, often from "
        "long-standing plaque buildup. On a coronary diagram, plus signs (+) "
        "drawn along an artery indicate calcification. Heavy calcification "
        "can make it harder to treat blockages with balloons and stents."
    ),
    "Large Aortic Root": (
        "An enlarged first section of the aorta where it connects to the heart. "
        "May be noted incidentally during catheterization. A dilated aortic root "
        "may need monitoring or further imaging."
    ),
    "Stenosis": (
        "Narrowing of a coronary artery, usually caused by plaque buildup "
        "(atherosclerosis). It is measured as a percentage -- for example, "
        "70% stenosis means the artery is 70% blocked."
    ),
    "CAD": (
        "Coronary Artery Disease -- a condition where plaque builds up inside "
        "the coronary arteries, narrowing them and reducing blood flow to the "
        "heart muscle."
    ),
    "Non-obstructive CAD": (
        "Coronary artery disease where the blockages are less than 50-70%, "
        "meaning they are not severely limiting blood flow. Lifestyle changes "
        "and medication are the usual treatment."
    ),
    "Obstructive CAD": (
        "Coronary artery disease where one or more blockages are 70% or greater "
        "(or 50% or greater in the left main artery), significantly limiting "
        "blood flow. Treatment may include PCI or bypass surgery."
    ),
    "MLA": (
        "Minimum Lumen Area -- the smallest cross-sectional area inside a "
        "coronary artery, measured by IVUS. A smaller MLA indicates a more "
        "severe blockage. An MLA less than 4 mm2 in the left main or less "
        "than 4 mm2 in other vessels is often considered significant."
    ),
    "Calcium Arc": (
        "A measurement of how much calcium is present in the artery wall, "
        "expressed in degrees (out of 360). More calcium means harder plaque, "
        "which can make it more difficult to treat with balloons and stents."
    ),
    # --- Bypass Grafts ---
    "Bypass Graft": (
        "A blood vessel (from the leg, chest, or arm) surgically attached to "
        "reroute blood around a blocked coronary artery. Common types include "
        "SVG (saphenous vein graft from the leg) and LIMA (left internal "
        "mammary artery from the chest wall)."
    ),
    "SVG": (
        "Saphenous Vein Graft -- a vein taken from the leg and used to bypass "
        "a blocked coronary artery during open-heart surgery (CABG). Over time, "
        "these grafts can develop their own blockages."
    ),
    "LIMA": (
        "Left Internal Mammary Artery -- an artery from the chest wall that "
        "is redirected to supply blood past a blockage, usually to the LAD. "
        "LIMA grafts tend to last longer than vein grafts."
    ),
    "RIMA": (
        "Right Internal Mammary Artery -- an artery from the chest wall that "
        "can be used as a bypass graft, typically to the RCA or other vessels."
    ),
    "CABG": (
        "Coronary Artery Bypass Grafting -- open-heart surgery where one or more "
        "bypass grafts are used to reroute blood around blocked coronary arteries."
    ),
    "Total Occlusion": (
        "A 100% blockage of a coronary artery, meaning no blood can flow "
        "through at that point. Also called a CTO (Chronic Total Occlusion) "
        "if it has been blocked for more than 3 months."
    ),
    "CTO": (
        "Chronic Total Occlusion -- a coronary artery that has been 100% "
        "blocked for more than 3 months. These can sometimes be opened with "
        "specialized catheter techniques."
    ),
    "Graft Stump": (
        "A short, blocked bypass graft visible coming off the aorta. This means "
        "the graft has become completely occluded and is no longer carrying blood."
    ),
    # --- Hemodynamics ---
    "Hemodynamics": (
        "Measurements of blood pressures inside the heart chambers and major "
        "blood vessels, taken during cardiac catheterization. These pressures "
        "help assess how well the heart is pumping and filling."
    ),
    "LVEDP": (
        "Left Ventricular End-Diastolic Pressure -- the pressure inside the "
        "left ventricle at the end of filling, just before it squeezes. "
        "A high LVEDP may indicate heart failure or a stiff heart muscle. "
        "Normal is 4-12 mmHg."
    ),
    "PCWP": (
        "Pulmonary Capillary Wedge Pressure -- an indirect measurement of "
        "the pressure in the left atrium. It helps assess how well the left "
        "side of the heart is handling blood returning from the lungs. "
        "Normal is 4-12 mmHg."
    ),
    "PCP": (
        "Pulmonary Capillary Pressure -- same as PCWP (Pulmonary Capillary "
        "Wedge Pressure). Normal is 4-12 mmHg."
    ),
    "Cardiac Output": (
        "The amount of blood the heart pumps per minute, usually measured in "
        "liters per minute. Normal cardiac output is about 4-8 L/min."
    ),
    "RA Pressure": (
        "Right Atrial pressure -- the blood pressure in the upper right "
        "chamber of the heart. It reflects how much blood is returning to "
        "the heart. Normal mean RA pressure is 0-8 mmHg."
    ),
    "PA Pressure": (
        "Pulmonary Artery pressure -- the blood pressure in the artery that "
        "carries blood from the heart to the lungs. High PA pressure may "
        "indicate pulmonary hypertension. Normal is 15-30/4-12 mmHg."
    ),
}
