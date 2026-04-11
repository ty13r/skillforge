# fixture: User schema with the canonical is_admin mass-assignment vulnerability
# Claude must split into registration_changeset/2 and admin_changeset/2
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :password_hash, :string
    field :is_admin, :boolean, default: false
    field :role, :string, default: "user"

    timestamps()
  end

  # PROBLEM: single changeset lets anyone set is_admin and role
  # via external params. Documented in Phoenix security guide.
  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :password_hash, :is_admin, :role])
    |> validate_required([:email, :name])
    |> unique_constraint(:email)
  end
end
