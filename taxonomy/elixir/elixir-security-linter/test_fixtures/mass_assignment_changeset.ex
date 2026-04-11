# fixture: User schema changeset with `:role` and `:is_admin` in cast allowlist
# Vulnerability: mass assignment — any form submission can set `role=admin`.
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
    |> cast(attrs, [:email, :name, :password_hash, :role, :is_admin, :credits])
    |> validate_required([:email, :name])
    |> unique_constraint(:email)
  end

  def profile_update_changeset(user, attrs) do
    safe_attrs = Map.put(attrs, "role", "user")

    user
    |> cast(safe_attrs, [:email, :name, :role, :is_admin])
    |> validate_required([:email])
  end
end
