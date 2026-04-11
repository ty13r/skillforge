defmodule MyApp.Auth do
  alias MyApp.{Repo, Session, Token, User}

  def authenticate(email, password) do
    with %User{} = user <- Repo.get_by(User, email: email) || {:error, :invalid_credentials},
         true <- User.check_password(user, password) || {:error, :invalid_credentials},
         {:ok, session} <- Session.create(user),
         {:ok, token} <- Token.issue(user, session) do
      {:ok, %{user: user, token: token}}
    end
  end

  def refresh(token_string) do
    with {:ok, claims} <- Token.decode(token_string),
         :ok <- Token.validate(claims),
         %User{} = user <- Repo.get(User, claims["user_id"]) || {:error, :user_deleted} do
      {:ok, user}
    end
  end
end
