# fixture: shared Profile schema — referenced by has_one preload challenges
defmodule MyApp.Accounts.Profile do
  use Ecto.Schema
  import Ecto.Changeset

  schema "profiles" do
    field :bio, :string
    field :avatar_url, :string
    field :twitter_handle, :string

    belongs_to :user, MyApp.Accounts.User

    timestamps(type: :utc_datetime)
  end

  def changeset(profile, attrs) do
    profile
    |> cast(attrs, [:bio, :avatar_url, :twitter_handle, :user_id])
    |> validate_required([:user_id])
  end
end
