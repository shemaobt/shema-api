from pydantic import BaseModel, EmailStr, Field


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str | None
    avatar_url: str | None = None
    is_active: bool
    is_platform_admin: bool
    locale: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = None
    locale: str | None = Field(default=None, max_length=10)


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class MyProjectRolesResponse(BaseModel):
    is_platform_admin: bool
    project_roles: dict[str, str]


class MyManagedOrgsResponse(BaseModel):
    managed_org_ids: list[str]


class MyManagedProjectsResponse(BaseModel):
    managed_project_ids: list[str]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    app_key: str = Field(max_length=100)


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class PasswordResetResponse(BaseModel):
    message: str
