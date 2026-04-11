# fixture: Multiple functions polluted with defensive nil checks. Real boothiq-style code
# where every function re-checks inputs the contract already guarantees.
defmodule MyApp.NotificationSender do
  alias MyApp.{Mailer, Repo, User}

  def send_welcome(user) do
    if is_nil(user) do
      {:error, :no_user}
    else
      email = user && user.email

      if is_nil(email) do
        {:error, :no_email}
      else
        template = build_template(user)

        if is_nil(template) do
          {:error, :template_failed}
        else
          Mailer.send(email, template)
        end
      end
    end
  end

  def build_template(user) do
    if user == nil do
      nil
    else
      preferences = user && user.preferences

      if is_nil(preferences) do
        default_template(user)
      else
        custom_template(user, preferences)
      end
    end
  end

  def default_template(user) do
    name = if is_nil(user.name), do: "friend", else: user.name
    "Welcome, #{name}!"
  end

  def custom_template(user, prefs) do
    language = prefs && prefs.language
    lang = if is_nil(language), do: "en", else: language
    greeting = if lang == "es", do: "Hola", else: "Welcome"
    "#{greeting}, #{user.name}!"
  end
end
