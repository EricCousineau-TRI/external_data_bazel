message(STATUS
    "Custom fetch"
    "${ExternalData_CUSTOM_LOCATION}"
    "${ExternalData_CUSTOM_FILE}"
)

set(ExternalData_CUSTOM_ERROR "Custom failure")

error("I want this to fail")
