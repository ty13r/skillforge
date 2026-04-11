# fixture: Nested case chains for auth flow. Should collapse into `with` + function heads.
defmodule MyApp.Auth do
  alias MyApp.{Repo, Session, Token, User}

  def authenticate(email, password) do
    case Repo.get_by(User, email: email) do
      nil ->
        {:error, :invalid_credentials}

      user ->
        case User.check_password(user, password) do
          true ->
            case Session.create(user) do
              {:ok, session} ->
                case Token.issue(user, session) do
                  {:ok, token} -> {:ok, %{user: user, token: token}}
                  {:error, reason} -> {:error, reason}
                end

              {:error, reason} ->
                {:error, reason}
            end

          false ->
            {:error, :invalid_credentials}
        end
    end
  end

  def refresh(token_string) do
    case Token.decode(token_string) do
      {:ok, claims} ->
        case Token.validate(claims) do
          :ok ->
            case Repo.get(User, claims["user_id"]) do
              nil -> {:error, :user_deleted}
              user -> {:ok, user}
            end

          {:error, reason} ->
            {:error, reason}
        end

      {:error, reason} ->
        {:error, reason}
    end
  end
end
