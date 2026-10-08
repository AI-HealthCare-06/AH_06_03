# alembic이 모든 테이블 설계도를 찾을 수 있게 여기서 한 번에 불러온다

from app.models.user import User, UserProfile, UserSession, GuardianConsentVerification
from app.models.health import HealthInputSchema, HealthMeasurement, HealthRecord  # noqa: F401
from app.models.survey import SurveyInstance, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion  # noqa: F401
from app.models.prediction import Prediction, PredictionFactor, PredictionJob  # noqa: F401
from app.models.calendar import CalendarEntry, HealthTodo  # noqa: F401