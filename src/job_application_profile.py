from dataclasses import dataclass

import yaml

from loguru import logger


@dataclass
class PersonalInformation:
    name: str
    surname: str
    date_of_birth: str
    country: str
    city: str
    address: str
    phone_prefix: str
    phone: str
    email: str
    github: str
    linkedin: str


@dataclass
class SelfIdentification:
    gender: str
    pronouns: str
    veteran: str
    disability: str
    ethnicity: str


@dataclass
class LegalAuthorization:
    eu_work_authorization: str
    us_work_authorization: str
    requires_us_visa: str
    legally_allowed_to_work_in_us: str
    requires_us_sponsorship: str
    requires_eu_visa: str
    legally_allowed_to_work_in_eu: str
    requires_eu_sponsorship: str
    canada_work_authorization: str
    requires_canada_visa: str
    legally_allowed_to_work_in_canada: str
    requires_canada_sponsorship: str
    uk_work_authorization: str
    requires_uk_visa: str 
    legally_allowed_to_work_in_uk: str
    requires_uk_sponsorship: str



@dataclass
class WorkPreferences:
    remote_work: str
    in_person_work: str
    open_to_relocation: str
    willing_to_complete_assessments: str
    willing_to_undergo_drug_tests: str
    willing_to_undergo_background_checks: str


@dataclass
class Availability:
    notice_period: str


@dataclass
class SalaryExpectations:
    salary_range_usd: str


@dataclass
class JobApplicationProfile:
    personal_information: PersonalInformation
    self_identification: SelfIdentification
    legal_authorization: LegalAuthorization
    work_preferences: WorkPreferences
    availability: Availability
    salary_expectations: SalaryExpectations

    def __init__(self, yaml_str: str):
        logger.debug("Initializing JobApplicationProfile with provided YAML string")
        try:
            data = yaml.safe_load(yaml_str)
            logger.debug(f"YAML data successfully parsed: {data}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise ValueError("Error parsing YAML file.") from e
        except Exception as e:
            logger.error(f"Unexpected error occurred while parsing the YAML file: {e}")
            raise RuntimeError("An unexpected error occurred while parsing the YAML file.") from e

        if not isinstance(data, dict):
            logger.error(f"YAML data must be a dictionary, received: {type(data)}")
            raise TypeError("YAML data must be a dictionary.")

        # Process personal_information
        try:
            logger.debug("Processing personal_information")
            self.personal_information = PersonalInformation(**data['personal_information'])
            logger.debug("personal_information processed: %s", self.personal_information)
        except KeyError as e:
            logger.error("Required field %s is missing in personal_information data.", e)
            raise KeyError(f"Required field {e} is missing in personal_information data.") from e
        except TypeError as e:
            logger.error("Error in personal_information data: %s", e)
            raise TypeError(f"Error in personal_information data: {e}") from e


        # Process self_identification
        try:
            logger.debug("Processing self_identification")
            self.self_identification = SelfIdentification(**data['self_identification'])
            logger.debug(f"self_identification processed: {self.self_identification}")
        except KeyError as e:
            logger.error(f"Required field {e} is missing in self_identification data.")
            raise KeyError(f"Required field {e} is missing in self_identification data.") from e
        except TypeError as e:
            logger.error(f"Error in self_identification data: {e}")
            raise TypeError(f"Error in self_identification data: {e}") from e
        except AttributeError as e:
            logger.error(f"Attribute error in self_identification processing: {e}")
            raise AttributeError("Attribute error in self_identification processing.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing self_identification: {e}")
            raise RuntimeError("An unexpected error occurred while processing self_identification.") from e

        # Process legal_authorization
        try:
            logger.debug("Processing legal_authorization")
            self.legal_authorization = LegalAuthorization(**data['legal_authorization'])
            logger.debug(f"legal_authorization processed: {self.legal_authorization}")
        except KeyError as e:
            logger.error(f"Required field {e} is missing in legal_authorization data.")
            raise KeyError(f"Required field {e} is missing in legal_authorization data.") from e
        except TypeError as e:
            logger.error(f"Error in legal_authorization data: {e}")
            raise TypeError(f"Error in legal_authorization data: {e}") from e
        except AttributeError as e:
            logger.error(f"Attribute error in legal_authorization processing: {e}")
            raise AttributeError("Attribute error in legal_authorization processing.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing legal_authorization: {e}")
            raise RuntimeError("An unexpected error occurred while processing legal_authorization.") from e

        # Process work_preferences
        try:
            logger.debug("Processing work_preferences")
            self.work_preferences = WorkPreferences(**data['work_preferences'])
            logger.debug(f"Work_preferences processed: {self.work_preferences}")
        except KeyError as e:
            logger.error(f"Required field {e} is missing in work_preferences data.")
            raise KeyError(f"Required field {e} is missing in work_preferences data.") from e
        except TypeError as e:
            logger.error(f"Error in work_preferences data: {e}")
            raise TypeError(f"Error in work_preferences data: {e}") from e
        except AttributeError as e:
            logger.error(f"Attribute error in work_preferences processing: {e}")
            raise AttributeError("Attribute error in work_preferences processing.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing work_preferences: {e}")
            raise RuntimeError("An unexpected error occurred while processing work_preferences.") from e

        # Process availability
        try:
            logger.debug("Processing availability")
            self.availability = Availability(**data['availability'])
            logger.debug(f"Availability processed: {self.availability}")
        except KeyError as e:
            logger.error(f"Required field {e} is missing in availability data.")
            raise KeyError(f"Required field {e} is missing in availability data.") from e
        except TypeError as e:
            logger.error(f"Error in availability data: {e}")
            raise TypeError(f"Error in availability data: {e}") from e
        except AttributeError as e:
            logger.error(f"Attribute error in availability processing: {e}")
            raise AttributeError("Attribute error in availability processing.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing availability: {e}")
            raise RuntimeError("An unexpected error occurred while processing availability.") from e

        # Process salary_expectations
        try:
            logger.debug("Processing salary_expectations")
            self.salary_expectations = SalaryExpectations(**data['salary_expectations'])
            logger.debug(f"salary_expectations processed: {self.salary_expectations}")
        except KeyError as e:
            logger.error(f"Required field {e} is missing in salary_expectations data.")
            raise KeyError(f"Required field {e} is missing in salary_expectations data.") from e
        except TypeError as e:
            logger.error(f"Error in salary_expectations data: {e}")
            raise TypeError(f"Error in salary_expectations data: {e}") from e
        except AttributeError as e:
            logger.error(f"Attribute error in salary_expectations processing: {e}")
            raise AttributeError("Attribute error in salary_expectations processing.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing salary_expectations: {e}")
            raise RuntimeError("An unexpected error occurred while processing salary_expectations.") from e

        logger.debug("JobApplicationProfile initialization completed successfully.")

    def __str__(self):
        logger.debug("Generating string representation of JobApplicationProfile")

        def format_dataclass(obj):
            return "\n".join(f"{field.name}: {getattr(obj, field.name)}" for field in obj.__dataclass_fields__.values())

        formatted_str = (f"Self Identification:\n{format_dataclass(self.self_identification)}\n\n"
                         f"Legal Authorization:\n{format_dataclass(self.legal_authorization)}\n\n"
                         f"Work Preferences:\n{format_dataclass(self.work_preferences)}\n\n"
                         f"Availability: {self.availability.notice_period}\n\n"
                         f"Salary Expectations: {self.salary_expectations.salary_range_usd}\n\n")
        logger.debug(f"String representation generated: {formatted_str}")
        return formatted_str
