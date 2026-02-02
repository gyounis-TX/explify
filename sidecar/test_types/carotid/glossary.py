"""
Carotid Doppler / Cerebrovascular Duplex glossary:
medical term -> plain English explanation.

Written at a 6th-8th grade reading level for patient-facing explanations.
"""

CAROTID_GLOSSARY: dict[str, str] = {
    # --- General ---
    "Carotid Doppler": (
        "An ultrasound test that uses sound waves to check the blood vessels "
        "in your neck (carotid arteries) that carry blood to your brain."
    ),
    "Cerebrovascular Duplex": (
        "Another name for a carotid doppler ultrasound. It combines a regular "
        "ultrasound image with Doppler flow measurements to evaluate the neck arteries."
    ),
    "Duplex Ultrasound": (
        "A test that combines two types of ultrasound: one to show the structure "
        "of the blood vessel and another to measure blood flow speed."
    ),
    # --- Anatomy ---
    "Common Carotid Artery (CCA)": (
        "The main artery in the neck that carries blood from the heart toward "
        "the brain. It splits into two branches higher up in the neck."
    ),
    "Internal Carotid Artery (ICA)": (
        "The branch of the carotid artery that goes directly to the brain. "
        "Narrowing here can increase stroke risk."
    ),
    "External Carotid Artery (ECA)": (
        "The branch of the carotid artery that supplies blood to the face, "
        "scalp, and neck. It does not go to the brain."
    ),
    "Vertebral Artery": (
        "A pair of arteries that run along the spine and supply blood to the "
        "back of the brain. They are also checked during a carotid ultrasound."
    ),
    # --- Measurements ---
    "Peak Systolic Velocity (PSV)": (
        "How fast blood is moving through the artery when the heart beats. "
        "Higher speeds may mean the artery is narrowed."
    ),
    "End Diastolic Velocity (EDV)": (
        "How fast blood is moving through the artery between heartbeats. "
        "A high EDV can indicate significant narrowing."
    ),
    "ICA/CCA Velocity Ratio": (
        "A comparison of blood speed in the internal carotid artery versus "
        "the common carotid artery. A higher ratio suggests more narrowing."
    ),
    # --- Pathology ---
    "Stenosis": (
        "Narrowing of a blood vessel, usually caused by plaque buildup on the "
        "artery wall. The percentage tells how much the artery is blocked."
    ),
    "Atherosclerosis": (
        "A condition where fatty deposits (plaque) build up inside artery walls, "
        "causing them to narrow and harden over time."
    ),
    "Plaque": (
        "A buildup of fat, cholesterol, and other substances on the inner wall "
        "of an artery. It can reduce blood flow or break off and cause a stroke."
    ),
    "Heterogeneous Plaque": (
        "Plaque that has a mixed appearance on ultrasound, containing both soft "
        "and hard material. This type may be less stable than uniform plaque."
    ),
    "Homogeneous Plaque": (
        "Plaque that has a uniform appearance on ultrasound. This type is "
        "generally considered more stable."
    ),
    "Calcified Plaque": (
        "Plaque that has hardened with calcium deposits. It appears bright "
        "on ultrasound and is generally more stable."
    ),
    # --- Flow ---
    "Antegrade Flow": (
        "Blood flowing in the normal, forward direction. This is a good sign "
        "that the artery is working properly."
    ),
    "Retrograde Flow": (
        "Blood flowing backward, opposite to the normal direction. This can "
        "indicate a blockage or abnormal circulation."
    ),
    "Patent": (
        "Open and unblocked. A patent artery means blood can flow through "
        "it normally."
    ),
    # --- Clinical ---
    "Hemodynamically Significant": (
        "Narrowing that is severe enough to affect blood flow. Generally, "
        "stenosis of 50% or more is considered hemodynamically significant."
    ),
    "Intima-Media Thickness (IMT)": (
        "The thickness of the inner two layers of the artery wall. Increased "
        "thickness can be an early sign of atherosclerosis."
    ),
}
