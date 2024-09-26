from abc import ABC, abstractmethod
from src.job import Job
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger


# An interface that defines different extraction strategies for the linkedin jobs page.
class Extractor(ABC):
    @abstractmethod
    def get_job_list(self, driver) -> list[Job]:
        pass


# The only extractor living in code as of writing this.
class Extractor1(Extractor):
    def get_job_list(self, driver) -> list[Job]:
        try:
            no_jobs_element = driver.find_element(
                By.CLASS_NAME, "jobs-search-two-pane__no-results-banner--expand"
            )
            if (
                "No matching jobs found" in no_jobs_element.text
                or "unfortunately, things aren" in driver.page_source.lower()
            ):
                logger.debug("No matching jobs found on this page, skipping")
                return []
        except NoSuchElementException:
            pass

        job_list_elements = driver.find_elements(
            By.CLASS_NAME, "scaffold-layout__list-container"
        )[0].find_elements(By.CLASS_NAME, "jobs-search-results__list-item")

        if not job_list_elements:
            logger.debug("No job class elements found on page, skipping")
            return

        job_list = [
            Job(*self.extract_job_information_from_tile(job_element))
            for job_element in job_list_elements
        ]
        return list(filter(lambda j: len(j.link) > 0, job_list))

    def extract_job_information_from_tile(self, job_tile):
        logger.debug("Extracting job information from tile")
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            print(job_tile.get_attribute("outerHTML"))
            job_title = (
                job_tile.find_element(By.CLASS_NAME, "job-card-list__title")
                .find_element(By.TAG_NAME, "strong")
                .text
            )

            link = (
                job_tile.find_element(By.CLASS_NAME, "job-card-list__title")
                .get_attribute("href")
                .split("?")[0]
            )
            company = job_tile.find_element(
                By.CLASS_NAME, "job-card-container__primary-description"
            ).text
            logger.debug(f"Job information extracted: {job_title} at {company}")
        except NoSuchElementException:
            logger.warning("Some job information (title, link, or company) is missing.")
        try:
            job_location = job_tile.find_element(
                By.CLASS_NAME, "job-card-container__metadata-item"
            ).text
        except NoSuchElementException:
            logger.warning("Job location is missing.")
        try:
            apply_method = job_tile.find_element(
                By.CLASS_NAME, "job-card-container__apply-method"
            ).text
        except NoSuchElementException:
            apply_method = "Applied"
            logger.warning("Apply method not found, assuming 'Applied'.")

        return job_title, company, job_location, link, apply_method


class Extractor2(Extractor):
    def get_job_list(self, driver) -> list[Job]:
        try:
            # Wait for the job list container to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "scaffold-layout__list-container")
                )
            )

            # Find the job list container
            job_list_container = driver.find_element(
                By.CLASS_NAME, "scaffold-layout__list-container"
            )

            # Find all job items within the container
            job_list_elements = job_list_container.find_elements(
                By.CSS_SELECTOR,
                "li.ember-view.jobs-search-results__list-item.occludable-update.p0.relative.scaffold-layout__list-item",
            )

            print(f"Number of job elements found: {len(job_list_elements)}")

            if not job_list_elements:
                raise Exception("No job elements found on page")

            job_list = [
                Job(*self.extract_job_information_from_tile(job_element))
                for job_element in job_list_elements
            ]
            return list(filter(lambda j: len(j.link) > 0, job_list))
        except Exception as e:
            return []

    def extract_job_information_from_tile(self, job_tile):
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            job_title = job_tile.find_element(
                By.CSS_SELECTOR, "a.job-card-list__title"
            ).text
            link = (
                job_tile.find_element(By.CSS_SELECTOR, "a.job-card-list__title")
                .get_attribute("href")
                .split("?")[0]
            )
            company = job_tile.find_element(
                By.CSS_SELECTOR, ".job-card-container__primary-description"
            ).text
            job_location = job_tile.find_element(
                By.CSS_SELECTOR, ".job-card-container__metadata-item"
            ).text
            apply_method = job_tile.find_element(
                By.CSS_SELECTOR, ".job-card-container__apply-method"
            ).text
        except NoSuchElementException as e:
            print(f"Error extracting job information: {str(e)}")

        return job_title, company, job_location, link, apply_method



# The only extractor living in code as of writing this.
class Extractor3(Extractor):
    def get_job_list(self, driver) -> list[Job]:
        try:
            no_jobs_element = driver.find_element(
                By.CLASS_NAME, "jobs-search-two-pane__no-results-banner--expand"
            )
            if (
                "No matching jobs found" in no_jobs_element.text
                or "unfortunately, things aren" in driver.page_source.lower()
            ):
                logger.debug("No matching jobs found on this page, skipping")
                return []
        except NoSuchElementException:
            pass

        job_list_elements = driver.find_elements(
            By.CLASS_NAME, "scaffold-layout__list-container"
        )[0].find_elements(By.CLASS_NAME, "jobs-search-results__list-item")

        if not job_list_elements:
            logger.debug("No job class elements found on page, skipping")
            return

        job_list = [
            Job(*self.extract_job_information_from_tile(job_element))
            for job_element in job_list_elements
        ]
        return list(filter(lambda j: len(j.link) > 0, job_list))

    def extract_job_information_from_tile(self, job_tile):
        job_title = link = company = job_location = apply_method = ""
        logger.debug("Extracting job information from tile")

        try:
            print(job_tile.get_attribute("outerHTML"))

            # Extract job title
            job_title = (
                job_tile.find_element(
                    By.CLASS_NAME, "job-card-job-posting-card-wrapper__title"
                )
                .find_element(By.TAG_NAME, "strong")
                .text
            )

            # Extract job link
            link = (
                job_tile.find_element(By.CLASS_NAME, "app-aware-link")
                .get_attribute("href")
            )

            # Extract company name
            company = job_tile.find_element(
                By.CLASS_NAME, "artdeco-entity-lockup__subtitle"
            ).text

            # Extract job location
            job_location = job_tile.find_element(
                By.CLASS_NAME, "artdeco-entity-lockup__caption"
            ).text

            # Apply method (if it exists)
            try:
                apply_method = job_tile.find_element(
                    By.CLASS_NAME, "job-card-job-posting-card-wrapper__footer-item"
                ).text
            except NoSuchElementException:
                logger.warning("Apply method not found for this job tile.")

            logger.debug(
                f"Job information extracted: {job_title} at {company}, located in {job_location}"
            )
        except NoSuchElementException:
            logger.warning(
                "Some job information (title, link, or company) could not be parsed."
            )
        


        return job_title, company, job_location, link, apply_method


EXTRACTORS = [Extractor1(), Extractor2(), Extractor3()]
