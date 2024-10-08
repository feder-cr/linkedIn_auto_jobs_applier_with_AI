import pytest
from src.job_application_profile import JobApplicationProfile

@pytest.fixture
def valid_yaml():
    """Valid YAML string for initializing JobApplicationProfile."""
    return """
    personal_information:
      name: John
      surname: Doe
      date_of_birth: "1990-01-01"
      country: USA
      city: New York
      address: "123 Main St"
      phone_prefix: "+1"
      phone: "1234567890"
      email: john.doe@example.com
      github: "github.com/johndoe"
      linkedin: "linkedin.com/in/johndoe"
    self_identification:
      gender: Male
      pronouns: He/Him
      veteran: No
      disability: No
      ethnicity: Asian
    legal_authorization:
      eu_work_authorization: "Yes"
      us_work_authorization: "Yes"
      requires_us_visa: "No"
      requires_us_sponsorship: "Yes"
      requires_eu_visa: "No"
      legally_allowed_to_work_in_eu: "Yes"
      legally_allowed_to_work_in_us: "Yes"
      requires_eu_sponsorship: "No"
      canada_work_authorization: "Yes"
      requires_canada_visa: "No"
      legally_allowed_to_work_in_canada: "Yes"
      requires_canada_sponsorship: "No"
      uk_work_authorization: "Yes"
      requires_uk_visa: "No"
      legally_allowed_to_work_in_uk: "Yes"
      requires_uk_sponsorship: "No"
    work_preferences:
      remote_work: "Yes"
      in_person_work: "No"
      open_to_relocation: "Yes"
      willing_to_complete_assessments: "Yes"
      willing_to_undergo_drug_tests: "Yes"
      willing_to_undergo_background_checks: "Yes"
    availability:
      notice_period: "2 weeks"
    salary_expectations:
      salary_range_usd: "80000-120000"
    """


@pytest.fixture
def missing_field_yaml():
    """YAML string missing a required field (self_identification)."""
    return """
    personal_information:
      name: John
      surname: Doe
      date_of_birth: "1990-01-01"
      country: USA
      city: New York
      address: "123 Main St"
      phone_prefix: "+1"
      phone: "1234567890"
      email: john.doe@example.com
      github: "github.com/johndoe"
      linkedin: "linkedin.com/in/johndoe"
    legal_authorization:
      eu_work_authorization: "Yes"
      us_work_authorization: "Yes"
      requires_us_visa: "No"
      requires_us_sponsorship: "Yes"
      requires_eu_visa: "No"
      legally_allowed_to_work_in_eu: "Yes"
      legally_allowed_to_work_in_us: "Yes"
      requires_eu_sponsorship: "No"
      canada_work_authorization: "Yes"
      requires_canada_visa: "No"
      legally_allowed_to_work_in_canada: "Yes"
      requires_canada_sponsorship: "No"
      uk_work_authorization: "Yes"
      requires_uk_visa: "No"
      legally_allowed_to_work_in_uk: "Yes"
      requires_uk_sponsorship: "No"
    work_preferences:
      remote_work: "Yes"
      in_person_work: "No"
      open_to_relocation: "Yes"
      willing_to_complete_assessments: "Yes"
      willing_to_undergo_drug_tests: "Yes"
      willing_to_undergo_background_checks: "Yes"
    availability:
      notice_period: "2 weeks"
    salary_expectations:
      salary_range_usd: "80000-120000"
    """


@pytest.fixture
def invalid_type_yaml():
    """YAML string with an invalid type for a field."""
    return """
    personal_information:
      name: John
      surname: Doe
      date_of_birth: "1990-01-01"
      country: USA
      city: New York
      address: "123 Main St"
      phone_prefix: "+1"
      phone: "1234567890"
      email: john.doe@example.com
      github: "github.com/johndoe"
      linkedin: "linkedin.com/in/johndoe"
    self_identification:
      gender: Male
      pronouns: He/Him
      veteran: No
      disability: No
      ethnicity: Asian
    legal_authorization:
      eu_work_authorization: "Yes"
      us_work_authorization: "Yes"
      requires_us_visa: "No"
      requires_us_sponsorship: "Yes"
      requires_eu_visa: "No"
      legally_allowed_to_work_in_eu: "Yes"
      legally_allowed_to_work_in_us: "Yes"
      requires_eu_sponsorship: "No"
      canada_work_authorization: "Yes"
      requires_canada_visa: "No"
      legally_allowed_to_work_in_canada: "Yes"
      requires_canada_sponsorship: "No"
      uk_work_authorization: "Yes"
      requires_uk_visa: "No"
      legally_allowed_to_work_in_uk: "Yes"
      requires_uk_sponsorship: "No"
    work_preferences:
      remote_work: 12345  # Invalid type, expecting a string
      in_person_work: "No"
      open_to_relocation: "Yes"
      willing_to_complete_assessments: "Yes"
      willing_to_undergo_drug_tests: "Yes"
      willing_to_undergo_background_checks: "Yes"
    availability:
      notice_period: "2 weeks"
    salary_expectations:
      salary_range_usd: "80000-120000"
    """


def test_initialize_with_valid_yaml(valid_yaml):
    """Test initializing JobApplicationProfile with valid YAML."""
    profile = JobApplicationProfile(valid_yaml)

    # Check that the profile fields are correctly initialized
    assert profile.self_identification.gender == "Male"
    assert profile.self_identification.pronouns == "He/Him"
    assert profile.legal_authorization.eu_work_authorization == "Yes"
    assert profile.work_preferences.remote_work == "Yes"
    assert profile.availability.notice_period == "2 weeks"
    assert profile.salary_expectations.salary_range_usd == "80000-120000"


def test_initialize_with_missing_field(missing_field_yaml):
    """Test initializing JobApplicationProfile with missing required fields."""
    with pytest.raises(KeyError) as excinfo:
        JobApplicationProfile(missing_field_yaml)
    assert "self_identification" in str(excinfo.value)


def test_initialize_with_invalid_yaml(invalid_type_yaml):
    """Test initializing JobApplicationProfile with invalid YAML field type."""
    profile = JobApplicationProfile(invalid_type_yaml)

    assert isinstance(profile.work_preferences.remote_work, str) is False
    assert profile.work_preferences.remote_work == 12345


def test_str_representation(valid_yaml):
    """Test the string representation of JobApplicationProfile."""
    profile = JobApplicationProfile(valid_yaml)
    profile_str = str(profile)

    assert "Self Identification:" in profile_str
    assert "Legal Authorization:" in profile_str
    assert "Work Preferences:" in profile_str
    assert "Availability:" in profile_str
    assert "Salary Expectations:" in profile_str
    assert "Male" in profile_str
    assert "80000-120000" in profile_str
