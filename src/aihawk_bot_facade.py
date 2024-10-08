from loguru import logger


class AIHawkBotState:
    def __init__(self):
        logger.debug("Initializing AIHawkBotState")
        self.reset()

    def reset(self):
        logger.debug("Resetting AIHawkBotState")
        self.credentials_set = False
        self.api_key_set = False
        self.job_application_profile_set = False
        self.gpt_answerer_set = False
        self.parameters_set = False
        self.logged_in = False

    def validate_state(self, required_keys):
        logger.debug(f"Validating AIHawkBotState with required keys: {required_keys}")
        for key in required_keys:
            if not getattr(self, key):
                logger.error(f"State validation failed: {key} is not set")
                raise ValueError(f"{key.replace('_', ' ').capitalize()} must be set before proceeding.")
        logger.debug("State validation passed")


class AIHawkBotFacade:
    def __init__(self, login_component, apply_component):
        logger.debug("Initializing AIHawkBotFacade")
        self.login_component = login_component
        self.apply_component = apply_component
        self.state = AIHawkBotState()
        self.job_application_profile = None
        self.resume = None
        self.email = None
        self.password = None
        self.parameters = None

    def set_job_application_profile_and_resume(self, job_application_profile, resume):
        logger.debug("Setting job application profile and resume")
        self._validate_non_empty(job_application_profile, "Job application profile")
        self._validate_non_empty(resume, "Resume")
        self.job_application_profile = job_application_profile
        self.resume = resume
        self.state.job_application_profile_set = True

        # Pass job_application_profile to apply_component (LinkedInJobManager)
        self.apply_component.set_job_application_profile(job_application_profile)

        logger.debug("Job application profile and resume set successfully")

    def set_secrets(self, email, password):
        logger.debug("Setting secrets: email and password")
        self._validate_non_empty(email, "Email")
        self._validate_non_empty(password, "Password")
        self.email = email
        self.password = password
        self.state.credentials_set = True
        logger.debug("Secrets set successfully")

    def set_gpt_answerer_and_resume_generator(self, gpt_answerer_component, resume_generator_manager):
        logger.debug("Setting GPT answerer and resume generator")
        self._ensure_job_profile_and_resume_set()
        gpt_answerer_component.set_job_application_profile(self.job_application_profile)
        gpt_answerer_component.set_resume(self.resume)
        self.apply_component.set_gpt_answerer(gpt_answerer_component)
        self.apply_component.set_resume_generator_manager(resume_generator_manager)
        self.state.gpt_answerer_set = True
        logger.debug("GPT answerer and resume generator set successfully")

    def set_parameters(self, parameters):
        logger.debug("Setting parameters")
        self._validate_non_empty(parameters, "Parameters")
        self.parameters = parameters
        self.apply_component.set_parameters(parameters)
        self.state.credentials_set = True
        self.state.parameters_set = True
        logger.debug("Parameters set successfully")

    def start_login(self):
        logger.debug("Starting login process")
        self.state.validate_state(['credentials_set'])
        self.login_component.start()
        self.state.logged_in = True
        logger.debug("Login process completed successfully")

    def start_apply(self):
        logger.debug("Starting apply process")
        self.state.validate_state(['logged_in', 'job_application_profile_set', 'gpt_answerer_set', 'parameters_set'])
        self.apply_component.start_applying()
        logger.debug("Apply process started successfully")

    def _validate_non_empty(self, value, name):
        logger.debug(f"Validating that {name} is not empty")
        if not value:
            logger.error(f"Validation failed: {name} is empty")
            raise ValueError(f"{name} cannot be empty.")
        logger.debug(f"Validation passed for {name}")

    def _ensure_job_profile_and_resume_set(self):
        logger.debug("Ensuring job profile and resume are set")
        if not self.state.job_application_profile_set:
            logger.error("Job application profile and resume are not set")
            raise ValueError("Job application profile and resume must be set before proceeding.")
        logger.debug("Job profile and resume are set")
