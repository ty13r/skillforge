# golden: User schema split into registration + admin changesets (fix mass assignment)
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :password_hash, :string
    field :is_admin, :boolean, default: false
    field :role, :string, default: "user"

    timestamps(type: :utc_datetime)
  end

  @doc "Public registration: never exposes privileged fields to external input."
  def registration_changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :password_hash])
    |> validate_required([:email, :name, :password_hash])
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/)
    |> unique_constraint(:email)
  end

  @doc "Profile update: user may change name only; not email or privileged fields."
  def profile_changeset(user, attrs) do
    user
    |> cast(attrs, [:name])
    |> validate_required([:name])
  end

  @doc "Admin-only: separate function, distinct cast list, called from admin context."
  def admin_changeset(user, attrs) do
    user
    |> cast(attrs, [:is_admin, :role])
    |> validate_inclusion(:role, ["user", "moderator", "admin"])
  end
end
