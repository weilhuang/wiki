package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"strings"
	"time"

	"example.com/reservation-service/internal/domain"
	"github.com/gin-gonic/gin"
)

const MaxBody int64 = 1024
const Budget = 2 * time.Second

type API struct {
	Service *domain.Service
	Tokens  map[string]domain.Principal
	Ready   func(context.Context) bool
}
type errorBody struct {
	Error struct {
		Code string `json:"code"`
	} `json:"error"`
}

func writeError(c *gin.Context, status int, code string) {
	var body errorBody
	body.Error.Code = code
	c.AbortWithStatusJSON(status, body)
}
func Status(code domain.Code) int {
	switch code {
	case domain.Unauthenticated:
		return 401
	case domain.PermissionDenied:
		return 403
	case domain.InvalidArgument:
		return 400
	case domain.NotFound:
		return 404
	case domain.Conflict, domain.OutOfStock:
		return 409
	case domain.Canceled:
		return 499
	case domain.Deadline:
		return 504
	case domain.OutcomeUnknown:
		return 503
	default:
		return 500
	}
}
func failure(c *gin.Context, err error) {
	code := domain.PublicCode(err)
	writeError(c, Status(code), string(code))
}
func (a *API) auth(write bool) gin.HandlerFunc {
	return func(c *gin.Context) {
		headers := c.Request.Header.Values("Authorization")
		if len(headers) != 1 {
			failure(c, domain.Fail(domain.Unauthenticated, nil))
			return
		}
		p, ok := a.Tokens[headers[0]]
		if !ok {
			failure(c, domain.Fail(domain.Unauthenticated, nil))
			return
		}
		if err := domain.Authorize(p, write); err != nil {
			failure(c, err)
			return
		}
		c.Set("principal", p)
		c.Next()
	}
}
func principal(c *gin.Context) domain.Principal { return c.MustGet("principal").(domain.Principal) }
func (a *API) Handler() http.Handler {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(func(c *gin.Context) { c.Header("Content-Type", "application/json"); c.Next() })
	r.Use(gin.CustomRecovery(func(c *gin.Context, _ any) { writeError(c, 500, "internal") }))
	r.GET("/live", func(c *gin.Context) { c.JSON(200, gin.H{"status": "live"}) })
	r.GET("/ready", func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 200*time.Millisecond)
		defer cancel()
		if a.Ready == nil || !a.Ready(ctx) {
			writeError(c, 503, "not_ready")
			return
		}
		c.JSON(200, gin.H{"status": "ready"})
	})
	r.POST("/v1/reservations", a.auth(true), a.reserve)
	r.GET("/v1/reservations/:operation_id", a.auth(false), a.get)
	r.NoRoute(func(c *gin.Context) { writeError(c, 404, "not_found") })
	return r
}
func (a *API) reserve(c *gin.Context) {
	media, params, err := mime.ParseMediaType(c.GetHeader("Content-Type"))
	if err != nil || media != "application/json" {
		writeError(c, 415, "unsupported_media_type")
		return
	}
	for key, value := range params {
		if key != "charset" || !strings.EqualFold(value, "utf-8") {
			writeError(c, 415, "unsupported_media_type")
			return
		}
	}
	body, err := io.ReadAll(http.MaxBytesReader(c.Writer, c.Request.Body, MaxBody))
	if err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			writeError(c, 413, "body_too_large")
		} else {
			writeError(c, 400, "body_read_failed")
		}
		return
	}
	in, err := Decode(body)
	if err != nil {
		writeError(c, 400, "invalid_json")
		return
	}
	ctx, cancel := context.WithTimeout(c.Request.Context(), Budget)
	defer cancel()
	op, err := a.Service.Reserve(ctx, principal(c), in)
	if err != nil {
		failure(c, err)
		return
	}
	c.JSON(200, op)
}
func (a *API) get(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), Budget)
	defer cancel()
	op, err := a.Service.Get(ctx, principal(c), c.Param("operation_id"))
	if err != nil {
		failure(c, err)
		return
	}
	c.JSON(200, op)
}
func Decode(body []byte) (in domain.Input, err error) {
	invalid := errors.New("invalid JSON contract")
	d := json.NewDecoder(bytes.NewReader(body))
	token, err := d.Token()
	if err != nil || token != json.Delim('{') {
		return in, invalid
	}
	fields := map[string]json.RawMessage{}
	for d.More() {
		token, err = d.Token()
		if err != nil {
			return in, invalid
		}
		key, ok := token.(string)
		if !ok {
			return in, invalid
		}
		if key != "operation_id" && key != "sku" && key != "quantity" {
			return in, invalid
		}
		if _, exists := fields[key]; exists {
			return in, invalid
		}
		var raw json.RawMessage
		if err = d.Decode(&raw); err != nil || bytes.Equal(raw, []byte("null")) {
			return in, invalid
		}
		fields[key] = raw
	}
	token, err = d.Token()
	if err != nil || token != json.Delim('}') || len(fields) != 3 {
		return in, invalid
	}
	if _, err = d.Token(); err != io.EOF {
		return in, invalid
	}
	if json.Unmarshal(fields["operation_id"], &in.OperationID) != nil || json.Unmarshal(fields["sku"], &in.SKU) != nil || json.Unmarshal(fields["quantity"], &in.Quantity) != nil {
		return in, invalid
	}
	return in, nil
}
