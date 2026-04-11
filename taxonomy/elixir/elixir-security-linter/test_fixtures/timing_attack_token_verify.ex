# fixture: Token verification using variable-time `==` on secrets
# Vulnerability: ==, pattern match with ^token, and hash equality all leak
# byte-by-byte timing. Fix uses Plug.Crypto.secure_compare/2.
defmodule MyApp.Auth.ApiKey do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def authenticate(user_id, token) do
    user = Repo.get!(User, user_id)

    if user.api_token == token do
      {:ok, user}
    else
      {:error, :invalid_token}
    end
  end

  def verify_webhook_signature(payload, signature, secret) do
    expected = :crypto.mac(:hmac, :sha256, secret, payload) |> Base.encode16()

    if expected == signature do
      :ok
    else
      :error
    end
  end

  # pattern-match timing leak
  def check_match(token, %{token: ^token}), do: :ok
  def check_match(_, _), do: :error
end
