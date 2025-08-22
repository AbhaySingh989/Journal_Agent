# Project Guiding Principles for Gemini CLI Development

## Mission Statement

This document establishes the foundational principles for all projects executed with the Gemini CLI. Our mission is to foster a development environment characterized by consistency, iterative progress, robust documentation, and deep user collaboration. By adhering to these guidelines, we ensure high-quality deliverables, transparent processes, and a structured approach to problem-solving and feature implementation.

## 1. Iterative Development Workflow

All projects will follow a mandatory iterative development cycle, ensuring continuous feedback and alignment with user expectations. Each iteration represents a self-contained unit of work, moving the project incrementally towards its goals.

### 1.1 Planning Phase

Each iteration begins with a clear, concise plan presented by the Gemini CLI to the user for explicit approval. This plan must detail:

*   **Objective:** The overarching goal for the current iteration, stated clearly and concisely.
    *   *Example:* "Implement user authentication via Telegram ID."
*   **Key Tasks:** A granular breakdown of the specific actions and steps required to achieve the objective. These should be actionable for the CLI.
    *   *Example:* "1. Create `Users` table in `bot_data.db` with `user_id`, `telegram_id`, `username`, `is_approved` fields. 2. Modify `/start` command handler to check/create user profile. 3. Add `is_approved` check for core bot functionality."
*   **Expected Deliverables:** The tangible outputs or changes that will result from the iteration.
    *   *Example:* "Database schema updated, `/start` command handles user registration, bot restricts unapproved users."
*   **Affected Files/Modules:** Identification of the specific files or logical modules within the codebase that will be modified or created.
    *   *Example:* "`bot/database.py`, `bot/handlers.py`, `bot/core.py`."

### 1.2 Implementation Phase

During implementation, the Gemini CLI will execute the approved plan, strictly adhering to existing project conventions, coding standards, and architectural patterns.

*   **Adherence to Conventions:** Mimic the style (formatting, naming), structure, framework choices, typing, and architectural patterns of existing code in the project. New libraries or frameworks will only be introduced if explicitly justified and approved.
*   **Idiomatic Changes:** Changes will be integrated naturally and idiomatically within the local context (imports, functions/classes).
*   **Code Comments:** Comments will be used sparingly, primarily to explain *why* a particular design choice was made, especially for complex algorithms, non-obvious logic, or workarounds. They will not describe *what* the code does if it's self-evident.

### 1.3 Review & Feedback Phase (User-in-the-Loop)

Upon completion of the implementation for an iteration, the Gemini CLI will present the changes and their impact to the user. This phase is critical for gathering immediate feedback and ensuring the work meets the user's requirements and vision.

*   **Presentation of Changes:** The CLI will provide a summary of the changes made, potentially including diffs or descriptions of new/modified functionality.
*   **Verification Instructions:** The CLI will provide clear instructions on how the user can test and verify the implemented changes.
*   **User Validation:** The user is expected to actively test the new functionality and provide feedback.

### 1.4 User Sign-off & Documentation Update

No iteration is considered complete without explicit "sign-off" from the user. This sign-off confirms that the user has reviewed the deliverables, provided feedback, and approved the current state of the project increment. Upon sign-off, the following documentation updates are mandatory:

*   **`Plan.md` Update:** The status of the completed iteration in `Plan.md` will be updated to "Completed" with the sign-off date.
*   **`README.md` Update:** The "Development Log" section of `README.md` will be updated with a new entry detailing the completed iteration's objective and sign-off status.
*   **`Product_Architecture.md` Update:** If the iteration involved significant architectural changes, new components, or modifications to the overall system design, `Product_Architecture.md` will be updated to reflect these changes.

## 2. Documentation Standards

Comprehensive and up-to-date documentation is paramount for project understanding, maintainability, and future collaboration.

### 2.1 `README.md` as the Project Hub

A `README.md` file is mandatory for every project and will serve as the primary source of truth for high-level project information. It must be continuously updated.

*   **Project Overview:** A concise description of the project's purpose, its primary features, and the problem it solves.
*   **Setup Instructions:** Step-by-step guide for setting up the development environment, including prerequisites, dependency installation (e.g., `pip install -r requirements.txt`), and initial configuration.
*   **Usage Guide:** Instructions on how to run the application, interact with its features, and common commands.
*   **Architecture Summary:** A high-level overview of the project's structure, key components, and the main technologies used. This should be a simplified version of `Product_Architecture.md`.
*   **Development Log:** A chronological record of completed iterations, including their objectives, key outcomes, and user sign-off dates.
    *   *Example Entry:* "Iteration 3: Implemented Journal Search Functionality. User Sign-off: 2025-07-05."

### 2.2 `Product_Architecture.md` for Technical Deep Dive

This file provides a detailed technical blueprint of the project, evolving as the project grows. It is updated when significant architectural decisions are made or major components are added/modified.

*   **System Overview:** Detailed breakdown of the system's components, their responsibilities, and how they interact (e.g., data flow diagrams, component diagrams).
*   **Technology Stack:** Comprehensive list of all technologies, frameworks, and major libraries used, with brief justifications for their selection.
*   **Data Models/Schemas:** Detailed descriptions or diagrams of database schemas, API request/response structures, and other data representations.
*   **API Contracts:** Definitions of internal and external API endpoints, including methods, parameters, and expected responses.
*   **Deployment Considerations:** Information relevant to deployment, such as environment variables, scaling strategies, and infrastructure requirements.
*   **Future Considerations/Roadmap:** High-level ideas for future enhancements, known limitations, or areas for refactoring.

### 2.3 `Plan.md` as the Product Backlog

This file serves as the living product backlog, tracking all planned, in-progress, and completed iterations. It provides transparency into the project's progress and future direction.

*   **Structure:** Each iteration will have a dedicated section with the following mandatory fields:
    *   **Iteration Number:** Unique identifier (e.g., "Iteration 1").
    *   **Objective:** The goal of the iteration (as defined in 1.1).
    *   **Status:** Current state (e.g., "Planned," "In Progress," "Awaiting Sign-off," "Completed").
    *   **Start Date:** When the iteration began (or is planned to begin).
    *   **End Date:** When the iteration was completed (or is estimated to complete).
    *   **User Sign-off:** "Yes" or "No," with the date of sign-off if applicable.
*   **Maintenance:** The Gemini CLI will update this file at the beginning of each planning phase and upon user sign-off of a completed iteration.
    *   *Example `Plan.md` Snippet:*
        ```markdown
        # Project Plan / Backlog

        ## Iteration 1: Initial Project Setup
        - Objective: Scaffold project, set up basic Flask app and webhook.
        - Status: Completed
        - Start Date: 2025-07-01
        - End Date: 2025-07-01
        - User Sign-off: Yes (2025-07-01)

        ## Iteration 2: User Authentication and Profile Management
        - Objective: Implement user registration, profile storage, and approval mechanism.
        - Status: Awaiting Sign-off
        - Start Date: 2025-07-02
        - End Date: 2025-07-04
        - User Sign-off: No

        ## Iteration 3: Journal Entry Storage
        - Objective: Migrate journal entries to SQLite database.
        - Status: Planned
        - Start Date: 2025-07-05 (Estimated)
        - End Date: 2025-07-07 (Estimated)
        - User Sign-off: No
        ```

### 2.4 In-Code Documentation

Code comments will be used sparingly and strategically, focusing on explaining *why* a particular approach was taken, especially for complex logic, rather than *what* is done. They should clarify non-obvious decisions, assumptions, or potential future considerations.

## 3. Architecture and Scalability

Projects will be developed with an eye towards long-term viability, maintainability, and adaptability.

### 3.1 Initial Architectural Analysis

At the outset of a project or when significant changes are requested, the Gemini CLI will perform an initial analysis of the existing (or proposed) architecture. This analysis aims to understand the current state and identify opportunities for improvement.

*   **Scope:** Review of existing code structure, data models, external integrations, and deployment environment.
*   **Identification:** Pinpoint core components, dependencies, potential bottlenecks, and areas that might hinder future scalability or maintenance.
*   *Example:* "Analyze `bot/core.py` for the main application loop, `bot/database.py` for data persistence patterns, and `app.py` for webhook handling. Identify potential for further modularization of AI interaction logic."

### 3.2 Scalability and Maintainability

Design decisions will proactively consider future scalability, performance, and ease of maintenance.

*   **Modularity:** Promote clear separation of concerns, ensuring distinct modules for different functionalities (e.g., UI/handlers, business logic, data access, external API interactions).
*   **Extensibility:** Design components to be easily extendable without requiring significant refactoring of existing, stable code.
*   **Error Handling:** Implement robust error handling and logging mechanisms to facilitate debugging and system stability.

### 3.3 Technology Choices

Any introduction of new libraries, frameworks, or significant technologies will be justified based on project requirements, existing conventions, and their impact on scalability and maintainability. Preference will be given to established, well-supported technologies.

## 4. Quality Assurance and Best Practices

A commitment to quality is embedded throughout the development process.

### 4.1 Testing

Where applicable and feasible, automated testing will be prioritized to ensure the reliability and correctness of implemented features and refactorings.

*   **Test Coverage:** Aim for appropriate test coverage for critical business logic and new features (e.g., unit tests for functions, integration tests for API endpoints).
*   **Verification:** The Gemini CLI will identify and utilize existing testing frameworks (e.g., `pytest`) and commands within the project to verify changes.
*   *Example:* "After implementing the search feature, run `pytest tests/test_database.py` to verify search logic."

### 4.2 Code Style and Linting

All code modifications will adhere to the project's established code style, formatting, and linting rules to maintain consistency and readability. The Gemini CLI will identify and run relevant linting/formatting tools (e.g., `ruff check .`, `black .`, `npm run lint`).

### 4.3 Security Considerations

Basic security best practices will be considered in all development activities, particularly when handling user input, sensitive data storage, and external API key management. This includes input validation, secure configuration, and avoiding hardcoding sensitive information.

### 4.4 Transparency and Communication

The Gemini CLI will maintain clear, concise, and direct communication with the user, providing necessary context for actions and seeking clarification when ambiguity arises.

### 4.5 Gemini Model during the session

The Gemini CLI will always use Gemini 2.5 pro model even if there's a latency, the Gemini CLI is not authorized to switch the Model without taking explicit permission from the user