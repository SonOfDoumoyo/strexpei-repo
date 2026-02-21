from fastapi import FastAPI, Request, status
from typing import Callable, Any
from fastapi.responses import JSONResponse


class StrexpeiException(Exception):
    """Exceptions for strexpei"""
 
    
class InvalidToken(StrexpeiException):
    """User has provided an invalid or expired token"""
    pass

class ExpiredToken(StrexpeiException):
    """USer has provided an expired token"""


class RevokedToken(StrexpeiException):
    """User has provided a token that has been revoked"""
    pass


class AccessTokenRequired(StrexpeiException):
    """User has provided a refresh token when an access token is needed"""
    pass


class CompanyTokenRequired(StrexpeiException):
    """User has provided a refresh token or a user token when a company access token is needed"""
    pass


class RefreshTokenRequired(StrexpeiException):
    """User has provided an access token when a refresh token is needed"""
    pass

class RefreshTokenExpired(StrexpeiException):
    """User has provided an expired or revoked refresh token"""

    
class UserAlreadyExists(StrexpeiException):
    """User has provided an email for a user who exists during sign up"""
    pass


class InvalidCredentials(StrexpeiException):
    """User has provided wrong email or password during log in"""
    pass


class InsufficientPermission(StrexpeiException):
    """User does not have the necessary permissions to perform an action"""
    pass


class UserNotFound(StrexpeiException):
    """User Not Found"""
    pass


class NoExistingUser(StrexpeiException):
    """Users do not exist yet"""
    pass


class AccountNotVerified(StrexpeiException):
    """Account not yet verified"""
    pass


class CompanyNotFound(StrexpeiException):
    """Organization not found"""
    pass

class StaffNotFound(StrexpeiException):
    """Staff not found"""
    pass    


class InactiveAccount(StrexpeiException):
    """Users account is not active"""


class PaymemtFailed(StrexpeiException):
    """Payment Failed"""
    pass
    
    
class InvalidBankDetails(StrexpeiException):
    """Invalid Bank details not found"""
    pass
    
    
class InvalidStaffCredentials(StrexpeiException):
    """User has provided incomplete or wrong details"""
    pass
    
    
class MembershipNotVerified(StrexpeiException):
    """Membership not verified by manager"""
    pass
    
    
class CompanyTokenRequired(StrexpeiException):
    """Organization token required"""
 

class InvalidAuthorizationCredentials(StrexpeiException):
    """User must have provided an invalid token"""


class InvalidOtpCode(StrexpeiException):
    """User provided an invalid OTP code"""

class WrongOtp(StrexpeiException):
    """User provided an invalid OTP code"""
    
class MaxOtpAttempts(StrexpeiException):
    """User provided an invalid OTP code"""
    

class TokenMisMatch(StrexpeiException):
    """Token mismatch"""
    
 
class AccountPendingError(StrexpeiException):
    """Raises Error for pending account"""
    

class AccountSuspendedError(StrexpeiException):
    """Raises Error for suspended account"""


class AccountBannedError(StrexpeiException):
    """Raises Error for banned account""" 
 
 
class AccountDeletedError(StrexpeiException):
    """Raises Error for disabled account"""
    

class InviteExpired(StrexpeiException):
    """Raises an errror for expired invitation"""


class CompanyDeletedError(StrexpeiException):
    """Raises error for unexpected error. during company deletion"""

class ExistingStaffConflict(StrexpeiException):
    """Raises an error for existing company staff that tries to join company agian"""




 
    
def create_exception_handler(status_code: int, initial_detail: Any) -> Callable[[Request, Exception], JSONResponse]:
    
    async def exception_handler(request: Request, exc:StrexpeiException):
        
        return JSONResponse(
            content=initial_detail,
            status_code=status_code
        )
    
    return exception_handler
    
def register_all_errors(app: FastAPI):
    app.add_exception_handler(
        UserAlreadyExists,
        create_exception_handler(
            status_code=status.HTTP_409_CONFLICT,
            initial_detail={
                "message":"User with email already exists",
                "error_code":"user_exists"
            },
        ),
    )


    app.add_exception_handler(
        CompanyDeletedError,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"company not deleted an error occured, check credentials and try again",
                "error_message":"company_not_deleted"
            },
        ),
    )


    app.add_exception_handler(
        InactiveAccount,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"your account is not active",
                "error_message":"inactive_account"
            },
        ),
    )


    app.add_exception_handler(
        ExistingStaffConflict,
        create_exception_handler(
            status_code=status.HTTP_409_CONFLICT,
            initial_detail={
                "message":"already a staff member of company",
                "error_message":"existing_staff_member"
            },
        ),
    )

    
    app.add_exception_handler(
        AccountSuspendedError,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"User account is suspended",
                "error_code":"account_suspended"
            },
        ),
    )

    app.add_exception_handler(
        StaffNotFound,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"User isn't a staff of company",
                "error_code":"not_a_staff"
            },
        ),
    )
    
    
    app.add_exception_handler(
        AccountDeletedError,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"Account doesn't exist",
                "error_code":"account_deleted"
            },
        ),
    )
    
    
    app.add_exception_handler(
        AccountPendingError,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"User account is pending approval",
                "error_code":"account_pending"
            },
        ),
    )
    
    
    app.add_exception_handler(
        AccountBannedError,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"User account is banned",
                "error_code":"account_banned"
            },
        ),
    )
    
    
    app.add_exception_handler(
        UserNotFound,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"User not found",
                "error_code":"user_not_found"
            },
        ),
    )
    
    
    app.add_exception_handler(
        NoExistingUser,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"Users not found",
                "error_code":"users_not_found"
            },
        ),
    )


    app.add_exception_handler(
        InvalidCredentials,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"Invalid email or password",
                "error_code":"inalid_email_or_password"
            },
        ),
    )
    
    
    app.add_exception_handler(
        InviteExpired,
        create_exception_handler(
            status_code=status.HTTP_410_GONE,
            initial_detail={
                "message":"invite is expired",
                "error_code":"expired_invitation"
            },
        ),
    )
    

    app.add_exception_handler(
        InvalidToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"Token is invalid or expired",
                "error_code":"invalid_token"
            },
        ),
    )


    app.add_exception_handler(
        ExpiredToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"Token is expired",
                "error_code":"expired_token"
            },
        ),
    )
    
    
    app.add_exception_handler(
        TokenMisMatch,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"Token doesn't match",
                "error_code":"token_mismatch"
            },
        ),
    )
    

    app.add_exception_handler(
        RevokedToken,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Token is invalid or has been revoked",
                "error_code":"token_revoked"
            },
        ),
    )


    app.add_exception_handler(
        AccessTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Please provide a valid access token",
                "error_code":"access_token_required"
            },
        ),
    )
    
    
    app.add_exception_handler(
        CompanyTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Please provide a valid company access token",
                "error_code":"company_access_token_required"
            },
        ),
    )
    

    app.add_exception_handler(
        RefreshTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Please provide a valid refresh token",
                "error_code":"refresh_token_required"
            },
        ),
    )
    
    
    app.add_exception_handler(
        RefreshTokenExpired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Expired or rovoked refresh token",
                "error_code":"expired_or_revoked_refresh_token"
            },
        ),
    )
    
    
    app.add_exception_handler(
        AccountNotVerified,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Account not verified",
                "error": "account_not_verified",
                "resolution": "Please check your email for verification details"
            },
        ),
    )


    app.add_exception_handler(
        InsufficientPermission,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message":"You are not allowed to perform this action",
                "error_code":"access_denied"
            },
        ),
    )


    app.add_exception_handler(
        CompanyTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Company token is required",
                "error_code":"company_token_required"
            },
        ),
    )


    app.add_exception_handler(
        PaymemtFailed,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"Payment failed",
                "error_code":"payment_failed"
            },
        ),
    )


    app.add_exception_handler(
        InvalidBankDetails,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"Bank details not valid check details and try again",
                "error_code":"invalid_bank_details"
            },
        ),
    )
    

    app.add_exception_handler(
        InvalidStaffCredentials,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            initial_detail={
                "message":"Please provide a valid refresh token",
                "error_code":"refresh_token_required"
            },
        ),
    )
    
    
    app.add_exception_handler(
        MembershipNotVerified,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"Your company membership has not been verified",
                "error": "membership_not_verified",
                "resolution": "Please contact your manager"
            },
        ),
    )

    app.add_exception_handler(
        CompanyNotFound,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message":"company not found",
                "error_code":"company_not_found"
            },
        ),
    )
    
    
    app.add_exception_handler(
        InvalidAuthorizationCredentials,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message":"invalid authorization credentials",
                "error_code":"invalid_auth_credentials"
            },
        ),
    )
    
    
    app.add_exception_handler(
        InvalidOtpCode,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"Invalid or expired OTP provided",
                "error_code":"invalid_otp"
            },
        ),
    )
    
    app.add_exception_handler(
        MaxOtpAttempts,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"max attempts reached",
                "error_code":"max_otp_attempts"
            }
        )
    )
    
    
    app.add_exception_handler(
        WrongOtp,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message":"Invalid OTP provided",
                "error_code":"invalid_otp"
            }
        )
    )
    

    
    @app.exception_handler(500)
    async def internal_server_error(request, exc):
        return JSONResponse(
            content={
                "message":"Oops! Something went wrong!!!",
                "error_code":"internal_server_error"
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )