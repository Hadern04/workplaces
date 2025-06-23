from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Workplace

def index(request):
    """Рендерит главную страницу."""
    return render(request, 'tracker/index.html')

@csrf_exempt
def workplace_api(request):
    """API для управления рабочими местами."""
    if request.method == 'GET':
        workplaces = Workplace.objects.all().values('id', 'name', 'bbox', 'is_confirmed')
        return JsonResponse(list(workplaces), safe=False)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_workplace = Workplace.objects.create(
                name=data['name'],
                bbox=data['bbox'],
                is_confirmed=False
            )
            return JsonResponse({'status': 'ok', 'id': new_workplace.id}, status=201)
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data'}, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
def workplace_detail_api(request, pk):
    """API для удаления конкретного рабочего места."""
    try:
        workplace = Workplace.objects.get(pk=pk)
    except Workplace.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'DELETE':
        workplace.delete()
        return HttpResponse(status=204)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
def workplace_confirm_api(request, pk):
    """API для подтверждения рабочего места."""
    try:
        workplace = Workplace.objects.get(pk=pk)
    except Workplace.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'POST':
        workplace.is_confirmed = True
        workplace.save()
        return JsonResponse({'status': 'ok'}, status=200)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
def workplace_report_api(request, pk):
    """API для получения отчета о занятости рабочего места."""
    try:
        workplace = Workplace.objects.get(pk=pk)
    except Workplace.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({
            'id': str(workplace.id),
            'name': workplace.name,
            'times': workplace.times
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=405)