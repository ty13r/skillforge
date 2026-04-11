# golden: mass-assignment fix — remove sensitive fields from cast allowlist
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :password_hash, :string
    field :role, :string, default: "user"
    field :is_admin, :boolean, default: false
    field :credits, :integer, default: 0

    timestamps()
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :password_hash])
    |> validate_required([:email, :name])
    |> unique_constraint(:email)
  end

  def profile_update_changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name])
    |> validate_required([:email])
  end

  # Admin-only changeset — never call with user-supplied params
  def role_changeset(user, attrs) do
    user
    |> cast(attrs, [:role, :is_admin])
    |> validate_inclusion(:role, ["user", "admin", "moderator"])
  end
end
