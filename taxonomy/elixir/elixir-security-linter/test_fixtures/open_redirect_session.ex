# fixture: Controller with open redirect after login
# Vulnerability: redirect to user-controlled param without allowlisting.
# Sets up CVE-2017-1000163-style regression (the `/\nevil.com` bypass).
defmodule MyAppWeb.SessionController do
  use MyAppWeb, :controller

  alias MyApp.Accounts

  def create(conn, %{"email" => email, "password" => password} = params) do
    case Accounts.authenticate(email, password) do
      {:ok, user} ->
        return_to = params["return_to"] || "/"

        conn
        |> put_session(:user_id, user.id)
        |> redirect(external: return_to)

      {:error, _} ->
        conn
        |> put_flash(:error, "Invalid credentials")
        |> render(:new)
    end
  end

  def oauth_callback(conn, %{"state" => state, "code" => _code}) do
    # state may encode a destination URL
    redirect(conn, external: state)
  end
end
