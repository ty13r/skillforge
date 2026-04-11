# golden: weak password hashing fix — use Bcrypt.hash_pwd_salt/1
defmodule MyApp.Accounts.Auth do
  alias MyApp.Accounts.User
  alias MyApp.Repo

  def register(attrs) do
    hash = Bcrypt.hash_pwd_salt(attrs["password"])

    %User{}
    |> User.changeset(Map.put(attrs, "password_hash", hash))
    |> Repo.insert()
  end

  def verify(email, password) do
    user = Repo.get_by(User, email: email)

    cond do
      user && Bcrypt.verify_pass(password, user.password_hash) ->
        {:ok, user}

      user ->
        {:error, :invalid_credentials}

      true ->
        Bcrypt.no_user_verify()
        {:error, :invalid_credentials}
    end
  end
end
