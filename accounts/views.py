from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.views import LoginView


class CustomLoginView(LoginView):
	template_name = 'registration/login.html'

	def form_valid(self, form):
		user = form.get_user()
		if user.role_utilisateurs.filter(role__nom__iexact='employé').exists():
			messages.error(self.request, "Accès refusé : votre compte n'a pas les droits nécessaires.")
			return self.form_invalid(form)
		return super().form_valid(form)
