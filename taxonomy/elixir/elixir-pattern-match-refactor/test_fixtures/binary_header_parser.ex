# fixture: Manual binary parsing using String ops where binary pattern matching would
# be the Elixir idiom. Extracting a 2-byte version, a 4-byte length, and a payload.
defmodule MyApp.PacketParser do
  def parse(<<_rest::binary>> = input) do
    if byte_size(input) < 6 do
      {:error, :too_short}
    else
      version = :binary.part(input, 0, 2)
      length_bytes = :binary.part(input, 2, 4)
      length = :binary.decode_unsigned(length_bytes)
      payload = :binary.part(input, 6, length)
      {:ok, %{version: version, length: length, payload: payload}}
    end
  end

  def strip_prefix(data) do
    if String.starts_with?(data, "HDR:") do
      rest_bytes = byte_size(data) - 4
      :binary.part(data, 4, rest_bytes)
    else
      data
    end
  end
end
