# golden: legendary refactor — god-schema split into registration, profile, admin changesets
# plus embedded profile for subordinate data
defmodule MyApp.Accounts.Profile do
  use Ecto.Schema
  import Ecto.Changeset

  embedded_schema do
    field :bio, :string
    field :avatar_url, :string
    field :phone, :string
  end

  def changeset(profile, attrs) do
    profile
    |> cast(attrs, [:bio, :avatar_url, :phone])
    |> validate_length(:bio, max: 2000)
  end
end

defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :password_hash, :string
    field :is_admin, :boolean, default: false
    field :role, :string, default: "user"
    field :subscription_tier, :string, default: "free"
    field :credit_balance, :decimal, default: 0

    embeds_one :profile, MyApp.Accounts.Profile, on_replace: :update

    timestamps(type: :utc_datetime)
  end

  def registration_changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :password_hash])
    |> validate_required([:email, :name, :password_hash])
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/)
    |> unique_constraint(:email)
  end

  def profile_changeset(user, attrs) do
    user
    |> cast(attrs, [:name])
    |> validate_required([:name])
    |> cast_embed(:profile, with: &MyApp.Accounts.Profile.changeset/2)
  end

  def admin_changeset(user, attrs) do
    user
    |> cast(attrs, [:is_admin, :role, :subscription_tier])
    |> validate_inclusion(:role, ["user", "moderator", "admin"])
    |> validate_inclusion(:subscription_tier, ["free", "pro", "enterprise"])
  end

  def credit_balance_changeset(user, attrs) do
    user
    |> cast(attrs, [:credit_balance])
    |> validate_number(:credit_balance, greater_than_or_equal_to: 0)
  end
end
