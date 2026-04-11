# fixture: Auth module storing passwords with :crypto.hash(:sha256, ...)
# Vulnerability: unsalted general-purpose hash — trivially reversed with
# rainbow tables. Must use bcrypt/argon2/pbkdf2 with a per-user salt.
defmodule MyApp.Accounts.Auth do
  alias MyApp.Accounts.User
  alias MyApp.Repo

  def register(attrs) do
    hash =
      :crypto.hash(:sha256, attrs["password"])
      |> Base.encode16(case: :lower)

    %User{}
    |> User.changeset(Map.put(attrs, "password_hash", hash))
    |> Repo.insert()
  end

  def verify(email, password) do
    user = Repo.get_by(User, email: email)
    expected_hash = :crypto.hash(:sha256, password) |> Base.encode16(case: :lower)

    if user && user.password_hash == expected_hash do
      {:ok, user}
    else
      {:error, :invalid_credentials}
    end
  end

  def legacy_md5_check(password, md5_hex) do
    :crypto.hash(:md5, password) |> Base.encode16(case: :lower) == md5_hex
  end
end
