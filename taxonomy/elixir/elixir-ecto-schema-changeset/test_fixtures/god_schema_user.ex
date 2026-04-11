# fixture: "God schema" User with registration, profile, and admin fields in one changeset.
# georgeguimaraes plugin: "Different operations = different changesets."
defmodule MyApp.Accounts.GodUser do
  use Ecto.Schema
  import Ecto.Changeset

  schema "god_users" do
    field :email, :string
    field :name, :string
    field :password_hash, :string
    field :phone, :string
    field :bio, :string
    field :avatar_url, :string
    field :is_admin, :boolean, default: false
    field :role, :string, default: "user"
    field :subscription_tier, :string, default: "free"
    field :credit_balance, :decimal, default: 0

    timestamps(type: :utc_datetime)
  end

  # PROBLEM: monolithic changeset leaks admin fields into registration.
  def changeset(user, attrs) do
    user
    |> cast(attrs, [
      :email, :name, :password_hash, :phone, :bio, :avatar_url,
      :is_admin, :role, :subscription_tier, :credit_balance
    ])
    |> validate_required([:email, :name, :password_hash])
    |> unique_constraint(:email)
  end
end
