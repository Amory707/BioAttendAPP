from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.contrib.auth import logout as auth_logout


class CustomLoginView(LoginView):
	template_name = 'registration/login.html'

	def form_valid(self, form):
		user = form.get_user()
		if user.role_utilisateurs.filter(role__nom__iexact='employé').exists():
			messages.error(self.request, "Accès refusé : votre compte n'a pas les droits nécessaires.")
			return self.form_invalid(form)
		return super().form_valid(form)


@login_required
def settings_view(request):
	return render(request, 'accounts/settings.html', {'current_session_key': request.session.session_key})


@login_required
def logout_all_sessions(request):
	"""
	Supprime toutes les sessions associées à l'utilisateur.
	Si le POST contient 'all'=='1', supprime aussi la session courante (déconnecte l'utilisateur).
	Sinon, supprime toutes les autres sessions en conservant la session actuelle.
	"""
	if request.method != 'POST':
		return redirect('accounts:settings')

	delete_current = request.POST.get('all') == '1'
	current_key = request.session.session_key
	user_id = str(request.user.id)

	sessions = Session.objects.all()
	removed = 0
	for s in sessions:
		try:
			data = s.get_decoded()
		except Exception:
			continue
		if str(data.get('_auth_user_id')) == user_id:
			if not delete_current and s.session_key == current_key:
				continue
			s.delete()
			removed += 1

	if removed:
		if delete_current:
			auth_logout(request)
			messages.success(request, 'Toutes les sessions ont été supprimées et vous avez été déconnecté.')
			return redirect('accounts:login')
		else:
			messages.success(request, 'Toutes les autres sessions actives ont été supprimées.')
	else:
		messages.info(request, "Aucune session trouvée à supprimer.")

	return redirect('accounts:settings')