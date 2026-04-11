# fixture: Order/LineItem schema pair — referenced by upserts, aggregates, window fn challenges
defmodule MyApp.Shop.Order do
  use Ecto.Schema
  import Ecto.Changeset

  schema "orders" do
    field :number, :string
    field :total, :decimal
    field :status, :string, default: "pending"
    field :placed_at, :utc_datetime

    belongs_to :customer, MyApp.Accounts.User, foreign_key: :user_id
    has_many :line_items, MyApp.Shop.LineItem

    timestamps(type: :utc_datetime)
  end

  def changeset(order, attrs) do
    order
    |> cast(attrs, [:number, :total, :status, :placed_at, :user_id])
    |> validate_required([:number, :user_id])
    |> unique_constraint(:number)
  end
end

defmodule MyApp.Shop.LineItem do
  use Ecto.Schema
  import Ecto.Changeset

  schema "line_items" do
    field :quantity, :integer
    field :unit_price, :decimal
    field :product_name, :string

    belongs_to :order, MyApp.Shop.Order

    timestamps(type: :utc_datetime)
  end

  def changeset(line_item, attrs) do
    line_item
    |> cast(attrs, [:quantity, :unit_price, :product_name, :order_id])
    |> validate_required([:quantity, :unit_price, :order_id])
  end
end
