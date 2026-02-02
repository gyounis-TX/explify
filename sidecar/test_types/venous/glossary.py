"""
Lower Extremity Venous Duplex glossary:
medical term -> plain English explanation.
"""

VENOUS_GLOSSARY: dict[str, str] = {
    "Venous Duplex Scan": (
        "An ultrasound test that checks the veins in your legs for blood clots "
        "and abnormal blood flow. It combines a regular ultrasound image with "
        "Doppler flow measurements."
    ),
    "Deep Vein Thrombosis (DVT)": (
        "A blood clot that forms in a deep vein, usually in the leg. DVT can be "
        "dangerous if the clot breaks loose and travels to the lungs."
    ),
    "Venous Reflux": (
        "When blood flows backward in a vein instead of moving toward the heart. "
        "This happens when the valves inside the vein are not working properly."
    ),
    "Greater Saphenous Vein (GSV)": (
        "The longest vein in the body, running from the foot up the inner leg "
        "to the groin. Problems with this vein are a common cause of varicose veins."
    ),
    "Lesser Saphenous Vein (LSV)": (
        "A vein that runs along the back of the lower leg. Like the greater "
        "saphenous vein, it can develop reflux leading to varicose veins."
    ),
    "Common Femoral Vein (CFV)": (
        "A large vein in the upper thigh that carries blood back to the heart. "
        "It is one of the main veins checked for blood clots."
    ),
    "Popliteal Vein": (
        "The vein behind the knee. Blood clots here are clinically significant "
        "and typically require treatment."
    ),
    "Compressibility": (
        "The ability of a vein to be squeezed flat with the ultrasound probe. "
        "A normal vein compresses easily. If it does not compress, a blood clot "
        "may be present."
    ),
    "Phasic Flow": (
        "Blood flow in a vein that changes with breathing. This is a normal "
        "pattern showing that blood is moving freely."
    ),
    "Spontaneous Flow": (
        "Blood flow that is seen in a vein without squeezing the leg. "
        "This is a normal finding."
    ),
    "Augmentation": (
        "An increase in blood flow seen when the calf or foot is squeezed. "
        "A normal response to augmentation means the vein is not blocked."
    ),
    "Reflux Time": (
        "How long blood flows backward in a vein after a test maneuver. "
        "More than 500 milliseconds (half a second) in the deep veins, or more "
        "than 1000 milliseconds in the saphenous veins, is considered abnormal."
    ),
    "Vein Diameter": (
        "The width of the vein measured on ultrasound. Larger diameters may "
        "indicate the vein is stretched or not functioning properly."
    ),
    "Patent": (
        "Open and unblocked. A patent vein means blood can flow through "
        "it normally and there is no clot."
    ),
    "Varicose Veins": (
        "Swollen, twisted veins that you can see just under the surface of "
        "the skin. They are caused by weak or damaged valves in the veins."
    ),
    "Chronic Venous Insufficiency": (
        "A condition where the veins in the legs have trouble sending blood "
        "back to the heart, leading to swelling, skin changes, and sometimes ulcers."
    ),
}
