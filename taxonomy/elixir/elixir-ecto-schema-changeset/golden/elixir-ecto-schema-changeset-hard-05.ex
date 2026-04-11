# golden: Customer with embedded primary address
defmodule MyApp.CRM.Address do
  use Ecto.Schema
  import Ecto.Changeset

  embedded_schema do
    field :street, :string
    field :city, :string
    field :postal_code, :string
    field :country, :string
  end

  def changeset(address, attrs) do
    address
    |> cast(attrs, [:street, :city, :postal_code, :country])
    |> validate_required([:street, :city, :postal_code, :country])
  end
end

defmodule MyApp.CRM.Customer do
  use Ecto.Schema
  import Ecto.Changeset

  schema "customers" do
    field :name, :string
    field :email, :string

    embeds_one :primary_address, MyApp.CRM.Address, on_replace: :update

    timestamps(type: :utc_datetime)
  end

  def changeset(customer, attrs) do
    customer
    |> cast(attrs, [:name, :email])
    |> validate_required([:name, :email])
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/)
    |> cast_embed(:primary_address, with: &MyApp.CRM.Address.changeset/2)
    |> unique_constraint(:email)
  end
end
