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
