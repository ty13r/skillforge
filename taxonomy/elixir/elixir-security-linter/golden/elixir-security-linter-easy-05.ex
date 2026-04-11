# golden: ecto fragment fix — use ^ pin operator with parameterized fragment
defmodule MyApp.Catalog do
  import Ecto.Query, warn: false

  alias MyApp.Repo
  alias MyApp.Catalog.Product

  def search_products(term) do
    like = "%" <> term <> "%"

    from(p in Product,
      where: fragment("name ILIKE ?", ^like) or fragment("description ILIKE ?", ^like)
    )
    |> Repo.all()
  end

  def products_created_after(date) do
    from(p in Product,
      where: p.inserted_at > ^date
    )
    |> Repo.all()
  end

  def find_by_id(id) do
    from(p in Product, where: p.id == ^id)
    |> Repo.one()
  end
end
