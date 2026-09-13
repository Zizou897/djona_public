from django.contrib import admin

from .models import Favorite, Interest, Vehicle, VehicleImage


class VehicleImageInline(admin.TabularInline):
    model = VehicleImage
    extra = 1


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'price', 'city', 'condition', 'is_verified', 'publish']
    list_filter = ['condition', 'fuel_type', 'transmission', 'is_verified', 'publish']
    search_fields = ['brand', 'model_name', 'city']
    prepopulated_fields = {'slug': ('brand', 'model_name', 'year')}
    inlines = [VehicleImageInline]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'user', 'session_key', 'created_at']
    list_filter = ['created_at']


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'vehicle', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'phone', 'vehicle__brand', 'vehicle__model_name']
