from abc import ABC, abstractmethod
from src import Job


# An interface that defines different extraction strategies for the linkedin jobs page.
class Extractor(ABC):
    @abstractmethod
    def get_job_list(self, driver) -> List[Job]:
        pass


# The extractor living in code as of writing this.
class Extractor1(Extractor):
    def get_job_list(self, driver) -> List[Job]:
        try:
            no_jobs_element = self.driver.find_element(
                By.CLASS_NAME, "jobs-search-two-pane__no-results-banner--expand"
            )
            if (
                "No matching jobs found" in no_jobs_element.text
                or "unfortunately, things aren" in self.driver.page_source.lower()
            ):
                logger.debug("No matching jobs found on this page, skipping")
                return
        except NoSuchElementException:
            pass

        job_list_elements = self.driver.find_elements(
            By.CLASS_NAME, "scaffold-layout__list-container"
        )[0].find_elements(By.CLASS_NAME, "jobs-search-results__list-item")

        if not job_list_elements:
            logger.debug("No job class elements found on page, skipping")
            return

        job_list = [
            Job(*self.extract_job_information_from_tile(job_element))
            for job_element in job_list_elements
        ]
        return job_list

    def extract_job_information_from_tile(self, job_tile):
        job_title = link = company = job_location = apply_method = ""
        logger.debug("Extracting job information from tile")
        for chain in EXTRACTION_CHAINS:
            try:
                print(job_tile.get_attribute("outerHTML"))
                job_title = (
                    job_tile.find_element(By.CLASS_NAME, chain["job_title"])
                    .find_element(By.TAG_NAME, "strong")
                    .text
                )

                link = (
                    job_tile.find_element(By.CLASS_NAME, chain["link"])
                    .get_attribute("href")
                    .split("?")[0]
                )
                company = job_tile.find_element(By.CLASS_NAME, chain["company"]).text
                logger.debug(f"Job information extracted: {job_title} at {company}")
                job_location = job_tile.find_element(
                    By.CLASS_NAME, chain["job_location"]
                ).text
                apply_method = job_tile.find_element(
                    By.CLASS_NAME, chain["apply_method"]
                ).text
            except NoSuchElementException:
                logger.warning(
                    "Some job information (title, link, or company) could not be parsed with chain."
                )

        return job_title, company, job_location, link, apply_method


# A class that implements the interface
class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def perimeter(self):
        return 2 * (self.width + self.height)
