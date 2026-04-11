# fixture: shared User schema — referenced by every query challenge
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :age, :integer
    field :active, :boolean, default: true
    field :role, :string, default: "member"
    field :last_login_at, :utc_datetime
    field :email_verified_at, :utc_datetime

    has_many :posts, MyApp.Blog.Post
    has_many :comments, MyApp.Blog.Comment
    has_one :profile, MyApp.Accounts.Profile
    belongs_to :team, MyApp.Accounts.Team

    timestamps(type: :utc_datetime)
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :age, :active, :role, :team_id])
    |> validate_required([:email, :name])
    |> unique_constraint(:email)
  end
end
