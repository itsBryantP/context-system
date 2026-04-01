# Sample Module

This is the overview of the sample module.

## Architecture

The system uses a layered architecture with clear separation of concerns.

### Components

- **API Layer**: Handles HTTP requests
- **Service Layer**: Business logic
- **Data Layer**: Database interactions

## API Endpoints

### GET /users

Returns a paginated list of users. Supports filtering by role and status.

Parameters:
- `page` (int): Page number, default 1
- `limit` (int): Items per page, default 20
- `role` (string): Filter by role

### POST /users

Creates a new user account.

Request body:
- `name` (string, required): User's full name
- `email` (string, required): Email address
- `role` (string): User role, default "viewer"

## Configuration

The system is configured via environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `API_KEY`: Authentication key
