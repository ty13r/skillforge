defmodule MyApp.NotificationSender do
  alias MyApp.Mailer

  def send_welcome(%{email: email} = user) when is_binary(email) do
    user
    |> build_template()
    |> deliver(email)
  end

  def send_welcome(%{email: nil}), do: {:error, :no_email}
  def send_welcome(nil), do: {:error, :no_user}

  defp build_template(%{preferences: %{language: "es"}, name: name}),
    do: "Hola, #{name || "friend"}!"

  defp build_template(%{preferences: %{language: _}, name: name}),
    do: "Welcome, #{name || "friend"}!"

  defp build_template(%{name: name}),
    do: "Welcome, #{name || "friend"}!"

  defp deliver(template, email), do: Mailer.send(email, template)
end
