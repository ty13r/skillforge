# fixture: handle_event bodies with "function head soup" — binding everything in the head
defmodule MyAppWeb.SettingsLive do
  use MyAppWeb, :live_view

  alias MyApp.Settings

  def mount(_params, %{"user_id" => user_id}, socket) do
    current_user = %{id: user_id}

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:form, Settings.form_for(current_user))
      |> assign(:saving?, false)

    {:ok, socket}
  end

  # ANTI-PATTERN: binding every param + every assign in the head produces "function head soup"
  def handle_event(
        "validate",
        %{
          "settings" => %{
            "theme" => theme,
            "email" => email,
            "notifications_enabled" => notifications,
            "timezone" => tz,
            "language" => lang,
            "two_factor" => two_factor,
            "newsletter_opt_in" => newsletter
          }
        } = _params,
        %{assigns: %{current_user: %{id: user_id}, saving?: false}} = socket
      ) do
    form =
      Settings.validate(user_id, %{
        "theme" => theme,
        "email" => email,
        "notifications_enabled" => notifications,
        "timezone" => tz,
        "language" => lang,
        "two_factor" => two_factor,
        "newsletter_opt_in" => newsletter
      })

    {:noreply, assign(socket, :form, form)}
  end

  def handle_event("save", _params, socket) do
    {:noreply, assign(socket, :saving?, true)}
  end
end
