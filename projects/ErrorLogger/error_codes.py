# Error code definitions for ErrorLogger and all project components
# Convention: [Type][Origin][Component][Subcomponent][Number]
# Example: EABS1 = Error, AI Service, Backend, Setup Model, 1

ERROR_CODE_DEFINITIONS = {
    # Setup/Model
    "IABS1": "Setup model script started.",
    "IABS2": "All required model files present.",
    "IABS3": "Model file downloaded successfully.",
    "IABS4": "Using Hugging Face Hub API for download.",
    "IABS5": "Gated model access detected.",
    "EABS1": "Missing required model files.",
    "EABS2": "Failed to download model file.",
    "EABS3": "Missing Hugging Face access token.",
    # Backend/Inference
    "IABB1": "Inference request received.",
    "IABB2": "Inference response sent.",
    "EABB1": "Inference failed.",
    "EABB2": "No available model for inference.",
    # Frontend
    "IAFX1": "Frontend transmission received.",
    "IAFX2": "Frontend transmission sent.",
    "EAFX1": "Frontend error occurred.",
    # General
    "E00000": "Python exception occurred.",
    "E00001": "React exception occurred.",
    # Health/Info
    "IAXX1": "Health check called.",
    # Add more codes as needed for other components/subcomponents
}

