import os
import re
import sys
from pathlib import Path
import yaml
import click
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from lib_resume_builder_AIHawk import Resume,StyleManager,FacadeManager,ResumeGenerator
from src.utils import chrome_browser_options
from src.llm.llm_manager import GPTAnswerer
from src.aihawk_authenticator import AIHawkAuthenticator
from src.aihawk_bot_facade import AIHawkBotFacade
from src.aihawk_job_manager import AIHawkJobManager
from src.job_application_profile import JobApplicationProfile
from loguru import logger

# Suppress stderr
sys.stderr = open(os.devnull, 'w')


class ConfigError(Exception):
    pass


class ConfigValidator:
    @staticmethod
    def validate_email(email: str) -> bool:
        return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

    @staticmethod
    def validate_yaml_file(yaml_path: Path) -> dict:
        try:
            with open(yaml_path, 'r') as stream:
                return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error reading file {yaml_path}: {exc}")
        except FileNotFoundError:
            raise ConfigError(f"File not found: {yaml_path}")

    def validate_config(config_yaml_path: Path) -> dict:
        """
        Validate and load configuration from a YAML file.

        This function validates the configuration file to ensure that all required keys are present
        and that the types of their values are correct. It checks for required sections like 'remote',
        'experience_level', 'jobTypes', 'positions', 'locations', and 'personal_information', among others.
        If any key is missing or has an invalid type, it raises a ConfigError.

        Args:
            config_yaml_path (Path): Path to the YAML configuration file.

        Returns:
            dict: A dictionary containing the validated configuration parameters.

        Raises:
            ConfigError: If a required key is missing or has an invalid type.
        """

        logger.info(f"Loading and validating config file: {config_yaml_path}")

        # Load the YAML configuration file
        parameters = ConfigValidator.validate_yaml_file(config_yaml_path)
        logger.debug(f"Loaded config file content: {parameters}")

        # Define required keys and their expected types
        required_keys = {
            'remote': bool,
            'experience_level': dict,
            'jobTypes': dict,
            'date': dict,
            'positions': list,
            'locations': list,
            'distance': int,
            'company_blacklist': list,
            'title_blacklist': list,
            'llm_model_type': str,
            'llm_model': str

        }

        # Validate each required key
        for key, expected_type in required_keys.items():
            if key not in parameters:
                # Handle optional blacklist keys by setting them as empty lists if missing
                if key in ['company_blacklist', 'title_blacklist']:
                    parameters[key] = []
                    logger.debug(f"Optional key '{key}' missing, set to empty list.")
                else:
                    logger.error(f"Missing key '{key}' in config file.")
                    raise ConfigError(f"Missing or invalid key '{key}' in config file {config_yaml_path}")
            elif not isinstance(parameters[key], expected_type):
                # Allow None values for blacklists, but otherwise check type validity
                if key in ['company_blacklist', 'title_blacklist'] and parameters[key] is None:
                    parameters[key] = []
                    logger.debug(f"Key '{key}' was None, set to empty list.")
                else:
                    logger.error(f"Invalid type for key '{key}' in config file. Expected {expected_type}, but got {type(parameters[key])}.")
                    raise ConfigError(f"Invalid type for key '{key}' in config file {config_yaml_path}. Expected {expected_type}, but got {type(parameters[key])}.")

        # Validate 'experience_level' section
        experience_levels = ['internship', 'entry', 'associate', 'mid-senior level', 'director', 'executive']
        for level in experience_levels:
            if not isinstance(parameters['experience_level'].get(level), bool):
                logger.error(f"Invalid value for experience level '{level}'. Expected a boolean (True/False). Current value: {parameters['experience_level'].get(level)}")
                raise ConfigError(f"Experience level '{level}' must be a boolean in config file {config_yaml_path}")

        # Validate 'jobTypes' section
        job_types = ['full-time', 'contract', 'part-time', 'temporary', 'internship', 'other', 'volunteer']
        for job_type in job_types:
            if not isinstance(parameters['jobTypes'].get(job_type), bool):
                logger.error(f"Invalid value for job type '{job_type}'. Expected a boolean (True/False). Current value: {parameters['jobTypes'].get(job_type)}")
                raise ConfigError(f"Job type '{job_type}' must be a boolean in config file {config_yaml_path}")

        # Validate 'date' filters section
        date_filters = ['all time', 'month', 'week', '24 hours']
        for date_filter in date_filters:
            if not isinstance(parameters['date'].get(date_filter), bool):
                logger.error(f"Invalid value for date filter '{date_filter}'. Expected a boolean (True/False). Current value: {parameters['date'].get(date_filter)}")
                raise ConfigError(f"Date filter '{date_filter}' must be a boolean in config file {config_yaml_path}")

        # Validate 'positions' list
        if not all(isinstance(pos, str) for pos in parameters['positions']):
            logger.error(f"Invalid value in 'positions'. All entries must be strings. Current values: {parameters['positions']}")
            raise ConfigError(f"'positions' must be a list of strings in config file {config_yaml_path}")

        # Validate 'locations' list
        if not all(isinstance(loc, str) for loc in parameters['locations']):
            logger.error(f"Invalid value in 'locations'. All entries must be strings. Current values: {parameters['locations']}")
            raise ConfigError(f"'locations' must be a list of strings in config file {config_yaml_path}")

        # Validate 'distance' field
        approved_distances = {0, 5, 10, 25, 50, 100}
        if parameters['distance'] not in approved_distances:
            logger.error(f"Invalid distance value '{parameters['distance']}'. Must be one of {approved_distances}.")
            raise ConfigError(f"Invalid distance value in config file {config_yaml_path}. Must be one of: {approved_distances}")

        for blacklist in ['company_blacklist', 'title_blacklist']:
            if not isinstance(parameters.get(blacklist), list):
                raise ConfigError(f"'{blacklist}' must be a list in config file {config_yaml_path}")
            if parameters[blacklist] is None:
                parameters[blacklist] = []

        logger.info("Configuration validated successfully.")

        return parameters

    @staticmethod
    def validate_secrets(secrets_yaml_path: Path) -> tuple:
        secrets = ConfigValidator.validate_yaml_file(secrets_yaml_path)
        mandatory_secrets = ['email', 'password','llm_api_key']

        for secret in mandatory_secrets:
            if secret not in secrets:
                raise ConfigError(f"Missing secret '{secret}' in file {secrets_yaml_path}")

        if not ConfigValidator.validate_email(secrets['email']):
            raise ConfigError(f"Invalid email format in secrets file {secrets_yaml_path}.")
        if not secrets['password']:
            raise ConfigError(f"Password cannot be empty in secrets file {secrets_yaml_path}.")
        return secrets['email'], str(secrets['password']), secrets['llm_api_key']
        if not secrets['llm_api_key']:
            raise ConfigError(f"llm_api_key cannot be empty in secrets file {secrets_yaml_path}.")
        return secrets['llm_api_key']

class FileManager:
    @staticmethod
    def find_file(name_containing: str, with_extension: str, at_path: Path) -> Path:
        return next((file for file in at_path.iterdir() if
                     name_containing.lower() in file.name.lower() and file.suffix.lower() == with_extension.lower()),
                    None)

    @staticmethod
    def validate_data_folder(app_data_folder: Path) -> tuple:
        if not app_data_folder.exists() or not app_data_folder.is_dir():
            raise FileNotFoundError(f"Data folder not found: {app_data_folder}")

        required_files = ['secrets.yaml', 'config.yaml', 'plain_text_resume.yaml']
        missing_files = [file for file in required_files if not (app_data_folder / file).exists()]

        if missing_files:
            raise FileNotFoundError(f"Missing files in the data folder: {', '.join(missing_files)}")

        output_folder = app_data_folder / 'output'
        output_folder.mkdir(exist_ok=True)
        return (
        app_data_folder / 'secrets.yaml', app_data_folder / 'config.yaml', app_data_folder / 'plain_text_resume.yaml',
        output_folder)

    @staticmethod
    def file_paths_to_dict(resume_file: Path | None, plain_text_resume_file: Path) -> dict:
        if not plain_text_resume_file.exists():
            raise FileNotFoundError(f"Plain text resume file not found: {plain_text_resume_file}")

        result = {'plainTextResume': plain_text_resume_file}

        if resume_file:
            if not resume_file.exists():
                raise FileNotFoundError(f"Resume file not found: {resume_file}")
            result['resume'] = resume_file

        return result


def init_browser() -> webdriver.Chrome:
    try:
        options = chrome_browser_options()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")


def create_and_run_bot(email, password, parameters, llm_api_key):
    try:
        logger.info("Starting bot initialization...")
        logger.debug(f"Email: {email}")
        logger.debug(f"Parameters: {parameters}")
        logger.debug(f"LLM API Key: {llm_api_key}")

        style_manager = StyleManager()
        logger.debug("StyleManager initialized successfully.")

        resume_generator = ResumeGenerator()
        logger.debug("ResumeGenerator initialized successfully.")

        logger.info("Reading plain text resume file...")
        with open(parameters['uploads']['plainTextResume'], "r", encoding='utf-8') as file:
            plain_text_resume = file.read()
        logger.debug(f"Plain text resume loaded: {plain_text_resume[:100]}...")  # Логируем первые 100 символов

        resume_object = Resume(plain_text_resume)
        logger.debug(f"Resume object created: {resume_object}")

        logger.info("Creating FacadeManager for resume generation...")
        resume_generator_manager = FacadeManager(
            llm_api_key, style_manager, resume_generator, resume_object, Path("data_folder/output")
        )
        logger.debug("FacadeManager initialized successfully.")

        os.system('cls' if os.name == 'nt' else 'clear')
        logger.info("Choosing resume style...")
        resume_generator_manager.choose_style()
        logger.info("Resume style chosen successfully.")
        os.system('cls' if os.name == 'nt' else 'clear')

        logger.info("Creating JobApplicationProfile object...")
        job_application_profile_object = JobApplicationProfile(plain_text_resume)
        logger.debug(f"JobApplicationProfile created: {job_application_profile_object}")

        logger.info("Initializing the browser...")
        browser = init_browser()
        logger.debug("Browser initialized successfully.")

        logger.info("Initializing job application component...")
        apply_component = AIHawkJobManager(browser)
        logger.debug(f"Job application component created: {apply_component}")

        logger.info("Creating AIHawkBotFacade object...")
        bot = AIHawkBotFacade(None, apply_component)
        logger.debug(f"Bot facade created: {bot}")

        logger.info("Setting secrets for the bot...")
        bot.set_secrets(email, password)
        logger.info("Secrets set successfully.")

        logger.info("Initializing login component...")
        login_component = AIHawkAuthenticator(driver=browser, bot_facade=bot)
        logger.debug(f"Login component created: {login_component}")

        bot.login_component = login_component
        logger.debug("Login component set in bot facade.")

        logger.info("Initializing GPT Answerer component...")
        gpt_answerer_component = GPTAnswerer(parameters, llm_api_key)
        logger.debug(f"GPT Answerer component created: {gpt_answerer_component}")


        logger.info("Setting job application profile and resume...")
        bot.set_job_application_profile_and_resume(job_application_profile_object, resume_object)
        logger.info("Job application profile and resume set successfully.")

        logger.info("Setting GPT Answerer and resume generator...")
        bot.set_gpt_answerer_and_resume_generator(gpt_answerer_component, resume_generator_manager)
        logger.info("GPT Answerer and resume generator set successfully.")

        logger.info("Setting additional parameters for the bot...")
        bot.set_parameters(parameters)
        logger.info("Parameters set successfully.")

        logger.info("Starting bot login process...")
        bot.start_login()
        logger.info("Login process completed successfully.")

        logger.info("Starting job application process...")
        bot.start_apply()
        logger.info("Job application process completed successfully.")

    except WebDriverException as e:
        logger.error(f"WebDriver error occurred: {e}")
    except Exception as e:
        logger.error("An unexpected error occurred in create_and_run_bot:")
        logger.exception(e)
        raise RuntimeError(f"Error running the bot: {str(e)}")



@click.command()
@click.option('--resume', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
              help="Path to the resume PDF file")
def main(resume: Path = None):
    try:
        data_folder = Path("data_folder")
        secrets_file, config_file, plain_text_resume_file, output_folder = FileManager.validate_data_folder(data_folder)

        parameters = ConfigValidator.validate_config(config_file)
        email, password, llm_api_key = ConfigValidator.validate_secrets(secrets_file)

        parameters['uploads'] = FileManager.file_paths_to_dict(resume, plain_text_resume_file)
        parameters['outputFileDirectory'] = output_folder

        create_and_run_bot(email, password, parameters, llm_api_key)
    except ConfigError as ce:
        logger.error(f"Configuration error: {str(ce)}")
        logger.error(f"Refer to the configuration guide for troubleshooting: https://github.com/feder-cr/AIHawk_AIHawk_automatic_job_application/blob/main/readme.md#configuration {str(ce)}")
    except FileNotFoundError as fnf:
        logger.error(f"File not found: {str(fnf)}")
        logger.error("Ensure all required files are present in the data folder.")
        logger.error("Refer to the file setup guide: https://github.com/feder-cr/AIHawk_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except RuntimeError as re:

        logger.error(f"Runtime error: {str(re)}")

        logger.error("Refer to the configuration and troubleshooting guide: https://github.com/feder-cr/AIHawk_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        logger.error("Refer to the general troubleshooting guide: https://github.com/feder-cr/AIHawk_AIHawk_automatic_job_application/blob/main/readme.md#configuration")

if __name__ == "__main__":
    main()
