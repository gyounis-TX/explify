"""
Echocardiography glossary: medical term -> plain English explanation.

Each definition is written at a 6th-8th grade reading level for
patient-facing explanations.
"""

ECHO_GLOSSARY: dict[str, str] = {
    # --- General ---
    "Echocardiogram": (
        "An ultrasound test that uses sound waves to create pictures of the heart. "
        "It shows the heart's size, shape, and how well it is pumping."
    ),
    "Transthoracic Echocardiogram": (
        "An echocardiogram performed by placing an ultrasound probe on the chest wall. "
        "This is the most common type of heart ultrasound."
    ),
    "Transesophageal Echocardiogram": (
        "An echocardiogram performed by passing a small ultrasound probe down the "
        "esophagus (the tube from your mouth to your stomach). This provides clearer "
        "images of some heart structures because the probe is closer to the heart."
    ),
    "Doppler": (
        "A technique used during an echocardiogram to measure the speed and direction "
        "of blood flow through the heart and blood vessels."
    ),
    # --- Chambers ---
    "Left Ventricle": (
        "The heart's main pumping chamber, located in the lower left. It pumps "
        "oxygen-rich blood out to the body through the aorta."
    ),
    "Right Ventricle": (
        "The lower right chamber of the heart. It pumps blood to the lungs to "
        "pick up oxygen."
    ),
    "Left Atrium": (
        "The upper left chamber of the heart. It receives oxygen-rich blood "
        "returning from the lungs and passes it to the left ventricle."
    ),
    "Right Atrium": (
        "The upper right chamber of the heart. It receives blood returning from "
        "the body and passes it to the right ventricle."
    ),
    "Septum": (
        "The wall of muscle that separates the left and right sides of the heart."
    ),
    "Interventricular Septum": (
        "The muscular wall between the left and right ventricles (lower chambers). "
        "If this wall is thicker than normal, it may suggest high blood pressure or "
        "other conditions."
    ),
    # --- Measurements ---
    "Ejection Fraction": (
        "The percentage of blood pumped out of the heart's main pumping chamber "
        "(left ventricle) with each heartbeat. A normal ejection fraction is about "
        "52-70%. A lower number means the heart is not pumping as strongly as it should."
    ),
    "LVEF": (
        "Left Ventricular Ejection Fraction -- the percentage of blood the left "
        "ventricle pumps out with each beat. Normal is typically 52-70%."
    ),
    "Fractional Shortening": (
        "A measurement of how much the left ventricle squeezes (shortens) with each "
        "heartbeat. It is another way to assess how well the heart is pumping. "
        "Normal is about 25-43%."
    ),
    "LVIDd": (
        "Left Ventricular Internal Diameter in Diastole -- the width of the left "
        "ventricle when it is relaxed and filling with blood. An enlarged measurement "
        "may indicate the heart is stretched or dilated."
    ),
    "LVIDs": (
        "Left Ventricular Internal Diameter in Systole -- the width of the left "
        "ventricle when it is squeezing to pump blood. It should be smaller than the "
        "diastolic measurement."
    ),
    "IVSd": (
        "Interventricular Septal Thickness in Diastole -- the thickness of the wall "
        "between the two lower heart chambers when the heart is relaxed. A thicker "
        "wall may indicate high blood pressure or hypertrophic cardiomyopathy."
    ),
    "LVPWd": (
        "Left Ventricular Posterior Wall Thickness in Diastole -- the thickness of "
        "the back wall of the left ventricle when the heart is relaxed. Like IVSd, "
        "increased thickness may indicate high blood pressure or other conditions."
    ),
    "Left Atrial Volume Index": (
        "A measurement of the size of the left atrium adjusted for body size. "
        "An enlarged left atrium may indicate longstanding high blood pressure, "
        "heart valve disease, or diastolic dysfunction. Normal is less than 34 mL/m2."
    ),
    "LAVI": (
        "Left Atrial Volume Index -- the size of the upper left heart chamber "
        "adjusted for body size. Normal is less than 34 mL/m2."
    ),
    # --- Valves ---
    "Mitral Valve": (
        "The valve between the left atrium and left ventricle. It opens to let blood "
        "flow from the upper to lower left chamber and closes to prevent blood from "
        "flowing backward."
    ),
    "Aortic Valve": (
        "The valve between the left ventricle and the aorta (the main artery leaving "
        "the heart). It opens when the heart pumps and closes to prevent blood from "
        "leaking back."
    ),
    "Tricuspid Valve": (
        "The valve between the right atrium and right ventricle. It controls blood "
        "flow from the upper to lower right chamber."
    ),
    "Pulmonic Valve": (
        "The valve between the right ventricle and the pulmonary artery, which "
        "carries blood to the lungs."
    ),
    # --- Valve Problems ---
    "Regurgitation": (
        "Backward leaking of blood through a heart valve that does not close properly. "
        "Some trace or mild regurgitation is common and usually not a concern."
    ),
    "Mitral Regurgitation": (
        "Backward leaking of blood through the mitral valve. Mild regurgitation is "
        "common and often harmless. Moderate to severe regurgitation may cause symptoms "
        "and require monitoring or treatment."
    ),
    "Aortic Regurgitation": (
        "Backward leaking of blood through the aortic valve into the left ventricle. "
        "This makes the heart work harder to pump enough blood to the body."
    ),
    "Tricuspid Regurgitation": (
        "Backward leaking of blood through the tricuspid valve. Trace or mild "
        "tricuspid regurgitation is very common and usually normal."
    ),
    "Stenosis": (
        "Narrowing of a heart valve that restricts blood flow. The heart must work "
        "harder to push blood through a narrowed valve."
    ),
    "Aortic Stenosis": (
        "Narrowing of the aortic valve, making it harder for the heart to pump blood "
        "to the body. Severity is measured by the valve area and pressure gradient."
    ),
    "Mitral Stenosis": (
        "Narrowing of the mitral valve, which restricts blood flow from the left "
        "atrium to the left ventricle."
    ),
    # --- Diastolic Function ---
    "Diastolic Function": (
        "How well the heart relaxes and fills with blood between heartbeats. "
        "Diastolic dysfunction means the heart is stiffer than normal and does not "
        "fill as easily, which can lead to fluid buildup."
    ),
    "Diastolic Dysfunction": (
        "A condition where the heart muscle is stiffer than normal and has difficulty "
        "relaxing to fill with blood. It is graded from Grade I (mild) to Grade III "
        "(severe). It is common with aging and high blood pressure."
    ),
    "E/A Ratio": (
        "The ratio of two blood flow speeds through the mitral valve, measured by "
        "Doppler. The 'E' wave represents early passive filling; the 'A' wave "
        "represents filling from the atrium contracting. This ratio helps assess "
        "diastolic function."
    ),
    "E/e' Ratio": (
        "A measurement that estimates the pressure inside the left ventricle when "
        "it fills. A higher E/e' ratio suggests higher filling pressures, which may "
        "indicate diastolic dysfunction. Normal is less than 8."
    ),
    "Deceleration Time": (
        "The time it takes for the early filling blood flow (E wave) to slow down. "
        "It helps assess how stiff the left ventricle is. Normal is about "
        "160-220 milliseconds."
    ),
    # --- Hemodynamics ---
    "RVSP": (
        "Right Ventricular Systolic Pressure -- an estimate of the blood pressure "
        "in the lungs' arteries (pulmonary pressure). Elevated RVSP may indicate "
        "pulmonary hypertension. Normal is less than 35 mmHg."
    ),
    "Pulmonary Hypertension": (
        "High blood pressure in the arteries that supply the lungs. It makes the "
        "right side of the heart work harder. RVSP on echocardiogram is used to "
        "estimate this pressure."
    ),
    "TAPSE": (
        "Tricuspid Annular Plane Systolic Excursion -- a measurement of how well "
        "the right ventricle is pumping. Normal is at least 1.7 cm. A lower value "
        "suggests the right side of the heart may be weak."
    ),
    # --- Other Structures ---
    "Aortic Root": (
        "The first section of the aorta (the body's main artery) where it connects "
        "to the heart. An enlarged aortic root may need monitoring."
    ),
    "Pericardium": (
        "The thin sac surrounding the heart. A pericardial effusion means there is "
        "extra fluid in this sac."
    ),
    "Pericardial Effusion": (
        "An abnormal collection of fluid in the sac around the heart. A small amount "
        "may be harmless, but a large effusion can compress the heart and require "
        "drainage."
    ),
    # --- Wall Motion ---
    "Wall Motion": (
        "How the heart muscle walls move when the heart beats. Normal wall motion "
        "means all parts of the heart are squeezing well. Abnormal wall motion may "
        "indicate damage from a heart attack or other condition."
    ),
    "Hypokinesis": (
        "Reduced movement of part of the heart wall. This may indicate an area of "
        "the heart that is not receiving enough blood flow or has been damaged."
    ),
    "Akinesis": (
        "Absence of movement in part of the heart wall, typically indicating "
        "significant damage, often from a heart attack."
    ),
    "Dyskinesis": (
        "Abnormal outward bulging of part of the heart wall during contraction. "
        "This usually indicates a damaged or scarred area of the heart."
    ),
    # --- Other Terms ---
    "LV Hypertrophy": (
        "Thickening of the left ventricle's muscle wall, often caused by long-standing "
        "high blood pressure. The heart muscle grows thicker because it has been "
        "working harder than normal."
    ),
    "Concentric Hypertrophy": (
        "A pattern of heart wall thickening where all walls become thicker but the "
        "chamber size stays normal. Often seen with high blood pressure."
    ),
    "Eccentric Hypertrophy": (
        "A pattern where the heart chamber enlarges (dilates) along with wall "
        "thickening. Can be seen with conditions that cause volume overload."
    ),
    "Aortic Valve Area": (
        "The effective opening area of the aortic valve. A smaller area means the "
        "valve is narrower (stenotic). Normal is greater than 2.0 cm2. Severe aortic "
        "stenosis is defined as less than 1.0 cm2."
    ),
}
