# alembic이 모든 테이블 설계도를 찾을 수 있게 여기서 한 번에 불러온다

from app.models.user import User, UserProfile, UserSession, GuardianConsentVerification
from app.models.health import HealthInputSchema, HealthMeasurement, HealthRecord  # noqa: F401
from app.models.survey import SurveyInstance, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion  # noqa: F401
from app.models.prediction import Prediction, PredictionFactor, PredictionJob  # noqa: F401
from app.models.calendar import CalendarEntry, HealthTodo  # noqa: F401
from app.models.deletion import AccountDeletionRequest  # noqa: F401
from app.models.consent import ConsentPolicy, UserConsent  # noqa: F401
from app.models.challenge import (  # noqa: F401
    Challenge, ChallengeCategory, ChallengeCycle, ChallengeLevel, ChallengeLog, CycleChallenge, UserClassification,
)
from app.models.eligibility import EligibilityAssessment  # noqa: F401
from app.models.admin_audit import AdminAuditLog  # noqa: F401
from app.models.access_log import AccessLog  # noqa: F401
from app.models.inquiry import Inquiry  # noqa: F401
from app.models.guest_inquiry import GuestInquiry  # noqa: F401
from app.models.notice import Notice  # noqa: F401
from app.models.pie import PieLedger  # noqa: F401
from app.models.community import (  # noqa: F401
    CommunityComment, CommunityLike, CommunityPost, CommunityProfile, CommunityReport,
)
from app.models.common_challenge import CommonChallenge, CommonChallengeCert, CommonChallengeParticipant  # noqa: F401
