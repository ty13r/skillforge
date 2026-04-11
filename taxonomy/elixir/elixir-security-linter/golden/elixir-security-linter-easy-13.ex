# golden: open redirect fix — allowlist to a static path
defmodule MyAppWeb.SessionController do
  use MyAppWeb, :controller

  alias MyApp.Accounts

  @allowed_redirects ["/", "/dashboard", "/profile", "/settings"]

  def create(conn, %{"email" => email, "password" => password} = params) do
    case Accounts.authenticate(email, password) do
      {:ok, user} ->
        return_to = sanitize_return_to(params["return_to"])

        conn
        |> put_session(:user_id, user.id)
        |> redirect(to: return_to)

      {:error, _} ->
        conn
        |> put_flash(:error, "Invalid credentials")
        |> render(:new)
    end
  end

  def oauth_callback(conn, %{"state" => _state, "code" => _code}) do
    redirect(conn, to: "/dashboard")
  end

  defp sanitize_return_to(nil), do: "/"

  defp sanitize_return_to(path) when is_binary(path) do
    if path in @allowed_redirects, do: path, else: "/"
  end

  defp sanitize_return_to(_), do: "/"
end
