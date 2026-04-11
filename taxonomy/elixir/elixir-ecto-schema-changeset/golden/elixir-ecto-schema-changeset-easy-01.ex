# golden: Product schema with :decimal price and UTC timestamps
defmodule MyApp.Catalog.Product do
  use Ecto.Schema
  import Ecto.Changeset

  schema "products" do
    field :name, :string
    field :sku, :string
    field :price, :decimal
    field :cost, :decimal
    field :weight_kg, :decimal
    field :in_stock, :boolean, default: true

    timestamps(type: :utc_datetime)
  end

  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :sku, :price, :cost, :weight_kg, :in_stock])
    |> validate_required([:name, :sku, :price])
    |> validate_number(:price, greater_than: 0)
    |> validate_number(:cost, greater_than_or_equal_to: 0)
    |> unique_constraint(:sku)
  end
end
