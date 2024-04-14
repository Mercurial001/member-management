from .models import QRCodeAttendance
from rest_framework.serializers import ModelSerializer


class QRCodeAttendanceSerializer(ModelSerializer):
    class Meta:
        model = QRCodeAttendance
        fields = '__all__'
