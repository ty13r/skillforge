# fixture: Intermediate variable assignment chains that should be pipe pipelines.
defmodule MyApp.TextProcessor do
  def normalize(input) do
    trimmed = String.trim(input)
    downcased = String.downcase(trimmed)
    stripped = String.replace(downcased, ~r/[^a-z0-9 ]/, "")
    collapsed = String.replace(stripped, ~r/\s+/, " ")
    final = String.trim(collapsed)
    final
  end

  def slugify(title) do
    a = String.trim(title)
    b = String.downcase(a)
    c = String.replace(b, " ", "-")
    d = String.replace(c, ~r/[^a-z0-9-]/, "")
    d
  end

  def summary(text) do
    words = String.split(text, " ")
    first_ten = Enum.take(words, 10)
    joined = Enum.join(first_ten, " ")
    result = joined <> "..."
    result
  end
end
