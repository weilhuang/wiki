package corelab

// Counter makes method-set behavior observable without invalid source files.
type Counter struct{ N int }

func (c Counter) Value() int { return c.N }
func (c *Counter) Add(n int) { c.N += n }

type Valuer interface{ Value() int }
type Adder interface{ Add(int) }

var _ Valuer = Counter{}
var _ Valuer = (*Counter)(nil)
var _ Adder = (*Counter)(nil)

// CopyValues copies outer elements; type parameters do not create deep copies.
func CopyValues[T any](src []T) []T {
	if src == nil {
		return nil
	}
	dst := make([]T, len(src))
	copy(dst, src)
	return dst
}
