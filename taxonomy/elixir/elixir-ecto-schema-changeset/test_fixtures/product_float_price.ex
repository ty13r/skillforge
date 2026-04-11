# fixture: Product schema with the canonical :float-for-money anti-pattern
# Claude must fix this to :decimal with precision/scale and UTC timestamps
defmodule MyApp.Catalog.Product do
  use Ecto.Schema
  import Ecto.Changeset

  schema "products" do
    field :name, :string
    field :sku, :string
    field :price, :float
    field :cost, :float
    field :weight_kg, :float
    field :in_stock, :boolean, default: true

    timestamps()
  end

  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :sku, :price, :cost, :weight_kg, :in_stock])
    |> validate_required([:name, :sku, :price])
  end
end
