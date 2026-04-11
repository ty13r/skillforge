# golden: timing-attack fix — use Plug.Crypto.secure_compare/2
defmodule MyApp.Auth.ApiKey do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def authenticate(user_id, token) do
    user = Repo.get!(User, user_id)

    if Plug.Crypto.secure_compare(user.api_token, token) do
      {:ok, user}
    else
      {:error, :invalid_token}
    end
  end

  def verify_webhook_signature(payload, signature, secret) do
    expected = :crypto.mac(:hmac, :sha256, secret, payload) |> Base.encode16()

    if Plug.Crypto.secure_compare(expected, signature) do
      :ok
    else
      :error
    end
  end

  def check_match(token, %{token: candidate}) do
    if Plug.Crypto.secure_compare(token, candidate), do: :ok, else: :error
  end
end
